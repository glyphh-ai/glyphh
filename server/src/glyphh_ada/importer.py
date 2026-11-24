"""An import, as a job: a file of cases (JSON Lines, CSV with a mapping, or a model's export) recorded into a model.

1. The whole file is read once to check every row and find its id, and so how many precedents it would add (ids the
   model holds replace their rows and add none). Past the org's cap (its plan's), the import is refused whole before
   anything is written, unless it was sent with `partial`, which records new cases up to the cap and refuses the rest.
2. The model's HNSW index is dropped (building it once is far faster than inserting into it row by row; reads scan
   meanwhile), and the file read again, recording limits.BATCH cases a transaction. A refused row is named (the first
   limits.REFUSALS_SHOWN) and the rest go in. Progress, and how far it got, are written as it goes: a worker that
   dies leaves the job to another, which goes on from there, and the ids make a row written twice one row.
3. Then learn and calibrate, once (an export brings what its model learned, which is kept when this model reads its
   cases as that one did), and the index is built.

An `ada_sqlite` file (an Ada SQLite precedent store, precedents.sqlite, or an export) goes through sqlite_import.py."""

import io
import json
import time
import zipfile
from collections.abc import Callable, Iterator
from typing import Any

import glyphh_spec
import psycopg

from glyphh_ada import catalog, files, ingest, jobs, limits, sqlite_import
from glyphh_ada.imported import Tally, cap_check, finish, keep_learned, model_for, record
from glyphh_ada.prepare import prepare, stored

Progress = Callable[[float], None]


class Source:
    """The import's file, read as rows as many times as the import needs; an export (a zip) read from memory."""

    def __init__(self, conn: psycopg.Connection, schema: str, job: dict[str, Any]) -> None:
        self.conn, self.schema, self.fid = conn, schema, str(job["id"])
        self.format, self.mapping = job["args"]["format"], job["args"].get("mapping") or {}
        self.archive: zipfile.ZipFile | None = None
        if self.format == "jsonl" and ingest.is_zip(files.reader(conn, schema, self.fid)):
            self.archive = zipfile.ZipFile(io.BytesIO(files.reader(conn, schema, self.fid).read()))

    def rows(self, spec: glyphh_spec.Spec, at: int = 0) -> Iterator[ingest.Row]:
        if self.archive is not None:
            return ingest.exported(self.archive, at)
        stream = files.reader(self.conn, self.schema, self.fid)
        return ingest.table(stream, spec, self.mapping, at) if self.format == "csv" else ingest.jsonl(stream, at)

    def exported(self) -> tuple[Any, dict[str, Any] | None]:
        """The exported model's active spec and what it learned; (None, None) for a file that is no export."""
        if self.archive is None:
            return None, None
        versions = json.loads(self.archive.read("spec.json"))
        return next(v["spec"] for v in versions if v["active"]), json.loads(self.archive.read("learned.json"))


def _cases(source: Source, model: glyphh_spec.Model, tally: Tally, at: int = 0) -> Iterator[tuple[int, dict]]:
    """Every row the spec takes, prepared; every other counted and named."""
    for n, case, refusal in source.rows(model.spec, at):
        if case is not None:
            try:
                yield n, stored(model, case) if source.archive is not None else prepare(model, case, source.fid, n)
                continue
            except glyphh_spec.SpecError as e:
                refusal = (e.path, str(e))
        tally.refuse(n, *refusal)  # type: ignore[misc]


def _plan(source: Source, model: glyphh_spec.Model, args: dict[str, Any], progress: Progress) -> Tally:
    """Pass 1: every row checked, the new ids counted, the cap applied."""
    tally = Tally()
    ids = [case["rid"] for _, case in _cases(source, model, tally)]
    tally.rows = len(ids)
    progress(5)
    cap_check(source.conn, source.schema, model.space.store, tally, ids, args.get("cap"), bool(args.get("partial")))
    tally.restart()
    progress(10)
    return tally


def _recorder(
    conn: psycopg.Connection, schema: str, job: dict[str, Any], model: glyphh_spec.Model, tally: Tally
) -> Callable[[list[dict[str, Any]], int], None]:
    """Writes a batch, then the job's progress and how far it got (the row it ended at)."""

    def write(batch: list[dict[str, Any]], row: int) -> None:
        if batch:
            record(model, batch)
            tally.recorded += len(batch)
            batch.clear()
        percent = round(10 + 70 * min(tally.recorded / max(tally.rows, 1), 1.0), 1)
        jobs.mark(conn, schema, str(job["id"]), "running", percent=percent, result={"done": row})

    return write


def run(conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress) -> dict[str, Any]:
    if job["args"]["format"] == "ada_sqlite":
        return sqlite_import.run(conn, schema, job, progress)
    started, source = time.monotonic(), Source(conn, schema, job)
    kept = keep_learned(conn, schema, catalog.live(conn, schema, job["model"]), *source.exported())
    found, model, store = model_for(conn, schema, job)  # after what was kept: an export's cases restate by it
    tally = _plan(source, model, job["args"], progress)
    store.drop_index()
    done = int((job.get("result") or {}).get("done", 0))  # how far a worker that died got
    write, batch, row = _recorder(conn, schema, job, model, tally), [], done
    for row, case in _cases(source, model, tally, done):
        if tally.allows(row, case["rid"]):
            batch.append(case)
        if len(batch) >= limits.BATCH:
            write(batch, row)
    write(batch, row)
    recorded = time.monotonic() - started
    out = {**tally.result(), **finish(conn, schema, found, store, kept, job["args"].get("learn", True), progress)}
    files.delete(conn, schema, source.fid)
    out["seconds"] = {"recorded": round(recorded, 2), "total": round(time.monotonic() - started, 2)}
    return out
