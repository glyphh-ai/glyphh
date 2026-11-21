"""A re-encode, as a job: a version whose spec changes what a stored case carries gets a store of its own, written
from the active one while that one goes on serving, then made active (versions.py).

1. Every precedent of the active store, a batch at a time: its stored situation cut to the new spec's roles and
   restated by it, encoded by its seed, dimension and lexicon, written with its outcomes into the new store (no index
   yet). Then the new store learns and calibrates (when it has what learning needs), and its index is built.
2. Writes went on meanwhile: what changed since the copy began is copied again, first freely, then under the model's
   write lock (which every write to its cases takes shared) together with the cases forgotten, the outcomes graded
   meanwhile and the switch itself, so no write is lost. The version counter moves before the lock is let go, so a
   write that waited on it opens the new store.

`sync` (a rollback to a version on another store): the same from step 2, into that version's own store, which first
gets back what it had learned. The store left behind remembers how far it was copied (meta `synced_seq`), so a
rollback to it copies only what changed after.

A re-encode runs on the kernel of the version it makes active (process.py routes it there): an upgrade to another Ada
version restates, encodes, learns and calibrates with the new kernel, reading the old store, and a rollback across Ada
versions copies with the old one (every installed kernel reads the same store format, registry.py)."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import glyphh_kernel as kernel
import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore
from psycopg import sql

from glyphh_ada import catalog, jobs, orgschema, restate, versions
from glyphh_ada.errors import Refusal
from glyphh_ada.imported import build_index
from glyphh_ada.pg import org_of
from glyphh_ada.situations import restated, set_learned

Progress = Callable[..., None]  # (percent, stage=None): jobs.Tracker
_CHANGED = (
    " WHERE (seq > %s OR NOT EXISTS (SELECT 1 FROM {t} t WHERE t.id = {s}.id)) AND seq > %s ORDER BY seq LIMIT {n}"
)
_SETTLE = (
    "DELETE FROM {t} t WHERE NOT EXISTS (SELECT 1 FROM {s} s WHERE s.id = t.id)",
    "UPDATE {t} t SET outcome = s.outcome FROM {s} s WHERE s.id = t.id AND t.outcome <> s.outcome",
    "DELETE FROM {outcomes} WHERE model = %(t)s",
    "INSERT INTO {outcomes} (model, id, output, value, ts) SELECT %(t)s, id, output, value, ts FROM {outcomes}"
    " WHERE model = %(s)s",
    "UPDATE {counts} SET n = (SELECT count(*) FROM {t}) WHERE model = %(t)s",
)


def _changed(source: PostgresStore, target: PostgresStore, since: int) -> Iterator[list[tuple]]:
    """The source's rows written after `since`, or that the target lacks, a batch at a time, oldest written first."""
    where = sql.SQL(_CHANGED).format(t=target._t["part"], s=source._t["part_name"], n=sql.Literal(restate.BATCH))
    after = 0
    while True:
        with source._conn.transaction(), source._conn.cursor(binary=True) as cur:
            rows = cur.execute(source._select() + where, (since, after)).fetchall()
        if not rows:
            return
        yield rows
        after = rows[-1][8]


def _put(source: PostgresStore, target: PostgresStore, model: glyphh_spec.Model, rows: list[tuple]) -> None:
    encoder = kernel.Space(dim=target.dim, seed=model.spec.seed, lexicon=model.settings.lexicon)
    named = restate.named(source, [r[0] for r in rows])
    out = []
    for rid, text, outcome, _, _, author, ts, _, _ in rows:
        situation = restated(json.loads(text), model.spec)
        glyph = encoder.encode(situation)
        row = kernel.Row(rid, json.dumps(situation, ensure_ascii=False), outcome, target.dim, glyph, author, ts, None)
        out.append((row, named.get(rid, [])))
    target.put_many(out)


def _top(store: PostgresStore) -> int:
    with store._conn.transaction(), store._conn.cursor() as cur:
        return int(cur.execute(store._q("SELECT coalesce(max(seq), 0) FROM {part}")).fetchone()[0])  # type: ignore[index]


def copy(source: PostgresStore, target: PostgresStore, model: glyphh_spec.Model, since: int, progress: Progress) -> int:
    """What changed in the source after `since`, restated into the target. Returns the source's top sequence then."""
    top, total, done = _top(source), max(source.count(), 1), 0
    for rows in _changed(source, target, since):
        _put(source, target, model, rows)
        done += len(rows)
        progress(min(done / total, 1.0))
    return top


def _settle(conn: psycopg.Connection, source: PostgresStore, target: PostgresStore) -> None:
    """The target made the source's: its cases forgotten since, its outcomes, its count."""
    t, s = target._t, source._t
    names = {"t": t["part"], "s": s["part"], "outcomes": s["outcomes"], "counts": s["counts"]}
    for text in _SETTLE:
        params = {"t": target.model, "s": source.model} if "%(" in text else None
        conn.execute(sql.SQL(text).format(**names), params)


def _switch(job: "Job", model: glyphh_spec.Model, top: int, bump: Callable[[], None]) -> None:
    """The last of the writes copied, and the version made active, under the model's write lock."""
    conn, source, target = job.conn, job.source, job.target
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (versions.write_lock(job.schema, job.name),))
        copy(source, target, model, top, lambda _: None)
        _settle(conn, source, target)
        source.set_meta("synced_seq", _top(target))
        versions.retire(conn, job.schema, job.found)
        versions.make_active(conn, job.schema, job.found, job.version)
        bump()  # before the commit: a write waiting on the lock then reads the new version


class Job:
    """One re-encode: the model, the version it makes active, the store it leaves and the one it writes."""

    def __init__(self, conn: psycopg.Connection, schema: str, job: dict[str, Any]) -> None:
        self.conn, self.schema, self.name = conn, schema, job["model"]
        self.found = catalog.live(conn, schema, self.name)
        self.version, self.sync = int(job["args"]["version"]), bool(job["args"].get("sync"))
        spec_json, self.key, _, gone, self.learned, _ = versions.row(conn, schema, self.found, self.version)
        if gone:
            raise Refusal("E_VERSION_GONE", f"Version {self.version}'s store was dropped.", 410)
        self.spec = glyphh_spec.Spec.from_json(spec_json)
        old = glyphh_spec.Spec.from_json(self.found.spec)
        self.source = PostgresStore(conn, schema, self.found.store, dim=old.dimension, readonly=True)
        self.source.readonly = False  # it keeps how far it was copied (synced_seq)
        self.target = catalog.store(conn, schema, self.key, self.spec.dimension)  # made when new, with no index
        orgschema.fence(conn, schema, org_of(schema))

    def model(self) -> glyphh_spec.Model:
        """The new version over its store, with whatever its store has learned."""
        model = glyphh_spec.Model(self.spec, store=self.target)
        model.refresh_every = None
        return model


def run(
    conn: psycopg.Connection, schema: str, job: dict[str, Any], progress: Progress, bump: Callable[[], None]
) -> dict[str, Any]:
    move = Job(conn, schema, job)
    if move.found.version == move.version:
        return {"version": move.version, "active": True, "copied": 0}
    versions.prune(conn, schema, move.found, move.key)
    out: dict[str, Any] = {"version": move.version, "store": "synced" if move.sync else "made"}
    since = 0
    if move.sync:
        set_learned(conn, schema, move.key, move.learned or {})
        since = int(move.target.meta("synced_seq") or 0)
    top = copy(move.source, move.target, move.model(), since, lambda f: progress(60 * f))
    if not move.sync:
        try:
            out["learned"] = jobs.fit(
                conn, schema, move.key, move.spec, "learn", lambda p, stage=None: progress(60 + p / 4, stage)
            )
        except Refusal as r:
            out["learned"] = {"error": {"code": r.code, "message": r.message}}
    build_index(move.target)
    progress(90)
    model = move.model()
    top = copy(move.source, move.target, model, top, lambda _: None)
    _switch(move, model, top, bump)
    out["precedents"] = move.target.count()
    return out
