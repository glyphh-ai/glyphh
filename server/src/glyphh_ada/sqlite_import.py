"""An `ada_sqlite` import: a kernel store in one SQLite file (a self-hosted runtime's precedents.sqlite, or a model's
SQLite export) moved into a model, a batch at a time.

When the file's glyphs are this model's (a sample of its cases, encoded again by this model's seed, dimension and
lexicon, give the glyphs the file holds, and its cases name only this model's roles), the kernel's own Space.merge
unions each batch into the model's store by precedent id, the glyphs copied as they are: an id the model holds keeps
its row, as merge does. Otherwise each case is a stored situation restated for this model and recorded, as an
export's are. What the file's model learned, and its temperatures, are kept when the glyphs are this model's; else
the model learns once at the end. The cap, the index and the progress are any import's (importer.py)."""

import itertools
import json
import os
import sqlite3
from collections.abc import Callable, Iterator
from typing import Any

import glyphh_kernel as kernel
import glyphh_spec
import numpy as np
import psycopg
from glyphh_postgres import PostgresStore

from glyphh_ada import catalog, files, jobs, limits
from glyphh_ada.errors import Refusal
from glyphh_ada.imported import Tally, cap_check, finish, model_for, record
from glyphh_ada.prepare import stored
from glyphh_ada.situations import set_learned, strip

Progress = Callable[[float], None]
SAMPLE: int = 20  # cases encoded again to tell whether the file's glyphs are this model's


class _Batch:
    """A batch of the file's rows, as the Store Space.merge reads."""

    path, readonly = None, True

    def __init__(self, rows: list[kernel.StoredRow], named: list[tuple[str, str, str, float]]) -> None:
        self._rows, self._named = rows, named

    def encoding(self) -> int:
        return kernel.ENCODING

    def rows(self, by_time: bool = True) -> list[kernel.StoredRow]:
        return self._rows

    def named(self) -> list[tuple[str, str, str, float]]:
        return self._named


class _Held:
    """The model's store as merge sees it for one batch: only the batch's ids it holds, so it loads no more."""

    def __init__(self, store: PostgresStore, ids: list[str]) -> None:
        self.store, self.ids = store, ids

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def rows(self, by_time: bool = True) -> list[kernel.StoredRow]:
        query = self.store._select() + self.store._q(" WHERE id = ANY(%s)")
        with self.store._conn.transaction(), self.store._conn.cursor(binary=True) as cur:
            return [self.store._stored(r) for r in cur.execute(query, (self.ids,)).fetchall()]

    def named(self) -> list[tuple[str, str, str, float]]:
        return []

    def taus(self) -> list[tuple[str, Any]]:
        return []


def _open(path: str, spec: glyphh_spec.Spec) -> kernel.SqliteStore:
    source = kernel.SqliteStore(path, readonly=True)
    try:
        dims = {r[3] for r in itertools.islice(source.rows(), SAMPLE)}
    except sqlite3.DatabaseError:
        source.close()
        raise Refusal("E_IMPORT", "This file is not a kernel store (an SQLite precedents file).", 422) from None
    if dims - {spec.dimension}:
        source.close()
        message = f"The file's glyphs have {sorted(dims)[0]} dimensions; this model's have {spec.dimension}."
        raise Refusal("E_IMPORT", message, 422, reason="dimension")
    return source


def _ours(source: kernel.SqliteStore, model: glyphh_spec.Model) -> bool:
    """Whether the file's glyphs and roles are this model's."""
    spec = model.spec
    encoder = kernel.Space(dim=spec.dimension, seed=spec.seed, lexicon=model.settings.lexicon)
    for _, text, _, dim, blob, _, _, events in itertools.islice(source.rows(), SAMPLE):
        situation = json.loads(text)
        mine = {k: v for k, v in situation.items() if k != glyphh_spec.INTERACTIONS}
        glyph = encoder.encode(situation, kernel._events_from_blob(events, dim))
        if strip(mine, spec) != mine or not np.array_equal(glyph, np.frombuffer(blob, dtype=np.int8)):
            return False
    return True


def _meta(path: str) -> dict[str, Any]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT key, value FROM meta WHERE key LIKE 'learned%' OR key LIKE 'tau%'").fetchall()
    return {k: json.loads(v) for k, v in rows}


def _batches(source: kernel.SqliteStore) -> Iterator[tuple[list[kernel.StoredRow], dict[str, list]]]:
    named: dict[str, list] = {}
    for rid, output, value, ts in source.named() or []:
        named.setdefault(rid, []).append((rid, output, value, ts))
    rows = iter(source.rows())
    while batch := list(itertools.islice(rows, limits.BATCH)):
        yield batch, {r[0]: named.get(r[0], []) for r in batch}


def _merge(model: glyphh_spec.Model, store: PostgresStore, rows: list, named: dict[str, list]) -> int:
    space = kernel.Space(
        dim=store.dim, seed=model.spec.seed, lexicon=model.settings.lexicon, store=_Held(store, list(named))
    )
    space.author = model.space.author
    return space.merge(_Batch(rows, [n for r in rows for n in named[r[0]]]))  # type: ignore[arg-type]


def _restated(model: glyphh_spec.Model, rows: list, named: dict[str, list]) -> int:
    cases = [
        stored(
            model,
            {
                "id": r[0],
                "situation": json.loads(r[1]),
                "outcome": r[2] or None,
                "ts": r[6],
                "author": r[5],
                "outcomes": {o: v for _, o, v, _ in named[r[0]]},
            },
        )
        for r in rows
    ]
    record(model, cases)
    return len(cases)


def _load(
    conn: psycopg.Connection,
    schema: str,
    job: dict[str, Any],
    path: str,
    source: kernel.SqliteStore,
    progress: Progress,
) -> dict[str, Any]:
    found, model, store = model_for(conn, schema, job)
    ours, kept = _ours(source, model), False
    if ours and store.count() == 0:  # what the file's model learned fits its cases, and nothing else is held
        set_learned(conn, schema, found.store, _meta(path))
        found, model, store = model_for(conn, schema, job)
        kept = True
    tally = Tally(rows=source.count())
    cap_check(conn, schema, store, tally, (r[0] for r in source.rows(by_time=False)), job["args"].get("cap"), False)
    store.drop_index()
    for rows, named in _batches(source):
        tally.recorded += _merge(model, store, rows, named) if ours else _restated(model, rows, named)
        percent = round(10 + 70 * tally.recorded / max(tally.rows, 1), 1)
        jobs.mark(conn, schema, str(job["id"]), "running", percent=percent)
    out = {**tally.result(), "glyphs": "kept" if ours else "encoded again"}
    out.update(finish(conn, schema, found, store, kept, job["args"].get("learn", True), progress))
    files.delete(conn, schema, str(job["id"]))
    return out


def run(conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress) -> dict[str, Any]:
    path = files.to_temp(conn, schema, str(job["id"]), ".sqlite")
    try:
        found = catalog.live(conn, schema, job["model"])
        source = _open(path, glyphh_spec.Spec.from_json(found.spec))
        try:
            return _load(conn, schema, job, path, source, progress)
        finally:
            source.close()
    finally:
        os.remove(path)
