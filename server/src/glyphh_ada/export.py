"""An export, as a job: everything of a model, back out, never locked in. The file is kept in the org's `files` and
fetched by a download link (the API signs it when the job is read: limits.LINK_TTL seconds).

- `jsonl`: a zip of precedents.jsonl (one line a precedent, {id, situation, outcome, outcomes, ts, author}, the
  situation as the model keeps it), spec.json (every version: {version, spec, note, made_by, made_at, active}) and
  learned.json (the active store's learned weights and temperatures). Imported into a model of the same spec it
  answers as this one does (importer.py).
- `ada_sqlite`: a kernel store written through SqliteStore, which kernel.Space(path=…) and a self-hosted runtime open
  as precedents.sqlite unchanged, glyphs, outcomes, learned weights and temperatures included.

Read a batch at a time by sequence (restate.batches), never the whole model in memory."""

import json
import os
import tempfile
import zipfile
from collections.abc import Callable
from typing import Any

import glyphh_kernel as kernel
import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore

from glyphh_ada import catalog, files, restate
from glyphh_ada.catalog import q
from glyphh_ada.situations import learned_of

Progress = Callable[[float], None]
_VERSIONS = """
    SELECT v.version, v.spec, v.note, v.made_by, v.made_at, v.version = m.active_version FROM {s}.spec_versions v
    JOIN {s}.models m ON m.id = v.model_id WHERE v.model_id = %s ORDER BY v.version
"""


def _versions(conn: psycopg.Connection, schema: str, found: catalog.Live) -> list[dict[str, Any]]:
    keys = ("version", "spec", "note", "made_by", "made_at", "active")
    rows = conn.execute(q(schema, _VERSIONS), (found.id,)).fetchall()
    return [dict(zip(keys, r, strict=True)) for r in rows]


def _each(store: PostgresStore, progress: Progress) -> Any:
    """Every precedent with its named outcomes, a batch at a time."""
    total, seen = max(store.count(), 1), 0
    for rows in restate.batches(store):
        named = restate.named(store, [r[0] for r in rows])
        yield rows, named
        seen += len(rows)
        progress(90 * min(seen / total, 1.0))


def _jsonl(
    conn: psycopg.Connection, schema: str, found: catalog.Live, store: PostgresStore, path: str, progress: Progress
) -> int:
    count = 0
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        with archive.open("precedents.jsonl", "w", force_zip64=True) as out:
            for rows, named in _each(store, progress):
                for rid, text, outcome, _, _, author, ts, _, _ in rows:
                    outcomes = {o: v for o, v, _ in named.get(rid, [])}
                    line = {"id": rid, "situation": json.loads(text), "outcome": outcome or None, "outcomes": outcomes}
                    out.write((json.dumps({**line, "ts": ts, "author": author}, ensure_ascii=False) + "\n").encode())
                    count += 1
        archive.writestr("spec.json", json.dumps(_versions(conn, schema, found), default=str, indent=1))
        archive.writestr("learned.json", json.dumps(learned_of(conn, schema, found.store), sort_keys=True))
    return count


def _sqlite(
    conn: psycopg.Connection, schema: str, found: catalog.Live, store: PostgresStore, path: str, progress: Progress
) -> int:
    target, count = kernel.SqliteStore(path), 0
    try:
        for rows, named in _each(store, progress):
            batch = [
                (
                    kernel.Row(rid, text, outcome, dim, bits.glyph(), author, ts, None if ev is None else bytes(ev)),
                    named.get(rid, []),
                )
                for rid, text, outcome, dim, bits, author, ts, ev, _ in rows
            ]
            target.put_many(batch)
            count += len(batch)
        for key, value in learned_of(conn, schema, found.store).items():
            target.set_meta(key, value)
    finally:
        target.close()
    return count


def run(conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress) -> dict[str, Any]:
    found = catalog.live(conn, schema, job["model"])
    spec = glyphh_spec.Spec.from_json(found.spec)
    store = PostgresStore(conn, schema, found.store, dim=spec.dimension, readonly=True)
    fmt = job["args"]["format"]
    with tempfile.TemporaryDirectory(prefix="ada-export-") as folder:  # SQLite's journal files with it
        path = os.path.join(folder, "export")
        count = (_sqlite if fmt == "ada_sqlite" else _jsonl)(conn, schema, found, store, path, progress)
        size = files.from_path(conn, schema, str(job["id"]), path)
    name = f"{job['model']}.v{found.version}" + (".sqlite" if fmt == "ada_sqlite" else ".zip")
    return {"format": fmt, "precedents": count, "bytes": size, "filename": name, "version": found.version}
