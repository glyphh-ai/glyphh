"""What every import shares (importer.py, sqlite_import.py): the model it writes, the tally of its rows, the plan's cap
on the precedents it adds, recording a batch, and the end (what was learned kept or learned once, the index built)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore
from psycopg import sql

from glyphh_ada import catalog, jobs, limits
from glyphh_ada.errors import Refusal
from glyphh_ada.situations import same_store, set_learned

Progress = Callable[[float], None]
HELD_BATCH: int = 10_000  # ids looked up at once
BUILD_MEMORY: str = "512MB"  # maintenance_work_mem while an index is built: the HNSW graph built in memory
_BUILD = (
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS {index} ON {part} USING hnsw ((glyph::bit({dim})) bit_hamming_ops)"
    " WITH (m = {m}, ef_construction = {efc})"
)


def build_index(store: PostgresStore) -> None:
    """The store's HNSW index, as the kernel makes it (PostgresStore.build_index), but CONCURRENTLY: the partition
    takes writes while it is built (minutes at a million precedents), which a plain CREATE INDEX would hold."""
    names = {"index": store._t["index"], "part": store._t["part"], "dim": sql.Literal(store.dim)}
    names |= {"m": sql.Literal(store.hnsw_m), "efc": sql.Literal(store.ef_construction)}
    conn = store._conn
    conn.execute(sql.SQL("SET maintenance_work_mem = {}").format(sql.Literal(BUILD_MEMORY)))
    try:
        conn.execute(sql.SQL(_BUILD).format(**names))
    except psycopg.Error:  # a concurrent build that fails leaves an invalid index, which IF NOT EXISTS would keep
        store.drop_index()
        raise
    finally:
        conn.execute("RESET maintenance_work_mem")


@dataclass
class Tally:
    rows: int = 0  # the file's cases, taken or not
    recorded: int = 0
    refused: int = 0
    refusals: list[dict[str, Any]] = field(default_factory=list)
    new: set[str] = field(default_factory=set)  # ids the model did not hold
    over: set[str] = field(default_factory=set)  # new ids past the cap, under `partial`

    def refuse(self, row: int, path: str, message: str) -> None:
        self.refused += 1
        if len(self.refusals) < limits.REFUSALS_SHOWN:
            self.refusals.append({"row": row, "path": path, "message": message})

    def restart(self) -> None:
        """Pass 2 finds the same refused rows again: counted once."""
        self.rows = self.rows + self.refused
        self.refused, self.refusals = 0, []

    def allows(self, row: int, rid: str | None) -> bool:
        if rid in self.over:
            self.refuse(row, "", "over the plan's cap on precedents (sent with partial)")
            return False
        return True

    def result(self) -> dict[str, Any]:
        added = len(self.new - self.over)
        return {
            "rows": self.rows,
            "recorded": self.recorded,
            "added": added,
            "replaced": max(self.recorded - added, 0),
            "refused": self.refused,
            "refusals": self.refusals,
        }


def model_for(
    conn: psycopg.Connection, schema: str, job: dict[str, Any]
) -> tuple[catalog.Live, glyphh_spec.Model, PostgresStore]:
    """The model the job writes, over its active store (made writable, its index left as it is)."""
    found = catalog.live(conn, schema, job["model"])
    spec = glyphh_spec.Spec.from_json(found.spec)
    store = catalog.store(conn, schema, found.store, spec.dimension)
    model = glyphh_spec.Model(spec, store=store, author=str(job.get("made_by") or "import"))
    model.refresh_every = None
    return found, model, store


def cap_check(
    conn: psycopg.Connection,
    schema: str,
    store: PostgresStore,
    tally: Tally,
    ids: Iterable[str],
    cap: int | None,
    partial: bool,
) -> None:
    """The new ids among these (in order, each once), and the org's cap applied to them: refused whole past it, or
    under `partial`, the new ids past it marked to be refused."""
    order = list(dict.fromkeys(ids))
    held: set[str] = set()
    for start in range(0, len(order), HELD_BATCH):
        held |= store.has_many(order[start : start + HELD_BATCH])
    new = [rid for rid in order if rid not in held]
    tally.new = set(new)
    if cap is None:
        return
    used = catalog.total(conn, schema)
    room = max(cap - used, 0)
    if len(new) <= room:
        return
    if not partial:
        message = f"This import adds {len(new):,} precedents to the {used:,} the org holds: its plan allows {cap:,}."
        raise Refusal("E_LIMIT", message, 403, reason="precedents", used=used, max=cap, adding=len(new))
    tally.over = set(new[room:])


def record(model: glyphh_spec.Model, cases: list[dict[str, Any]]) -> None:
    """One transaction of cases, each written under its own author (an export's cases keep theirs)."""
    runs: list[tuple[str, list[dict[str, Any]]]] = []
    for case in cases:
        author = case.pop("author", None) or model.space.author
        if not runs or runs[-1][0] != author:
            runs.append((author, []))
        runs[-1][1].append(case)
    with model.space.store._conn.transaction():  # type: ignore[union-attr]
        default = model.space.author
        for author, run in runs:
            model.space.author = author
            model.space.record_many(run)
        model.space.author = default


def keep_learned(
    conn: psycopg.Connection, schema: str, found: catalog.Live, spec_json: Any, learned: dict[str, Any] | None
) -> bool:
    """What an exported model learned, kept by this one when it reads its cases as that one did and holds no others
    (what it learned of them is its own). Returns whether."""
    if learned is None or catalog.count(conn, schema, found.store):
        return False
    theirs, ours = glyphh_spec.Spec.from_json(spec_json), glyphh_spec.Spec.from_json(found.spec)
    if not same_store(theirs, ours):
        return False
    set_learned(conn, schema, found.store, learned)
    return True


def finish(
    conn: psycopg.Connection,
    schema: str,
    found: catalog.Live,
    store: PostgresStore,
    kept: bool,
    learn: bool,
    progress: Progress,
) -> dict[str, Any]:
    """Learned once (unless what an export learned was kept, or the import asked not to), then the index built."""
    out: dict[str, Any] = {"learned": "kept" if kept else None}
    if learn and not kept:
        spec = glyphh_spec.Spec.from_json(found.spec)
        try:
            out["learned"] = jobs.fit(
                conn, schema, found.store, spec, "learn", lambda p, stage=None: progress(80 + p * 0.15, stage)
            )
        except Refusal as r:
            out["learned"] = {"error": {"code": r.code, "message": r.message}}
    progress(95)
    build_index(store)
    return out
