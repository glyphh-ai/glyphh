"""Reading a store in batches by its sequence (what restating, re-encoding and exporting a model need without holding
it in memory), and restating a model's store after learning changed what a case carries (its learned word weights or
pairs): every precedent the job did not hold in memory, passed through the learned spec's restate and encoded again
as the kernel's Space.rewrite does, then written back a batch at a time."""

import json
from collections.abc import Callable, Container, Iterator

import glyphh_kernel as kernel
import glyphh_spec
from glyphh_postgres import PostgresStore
from psycopg import sql

from glyphh_ada import limits

BATCH: int = limits.BATCH
# A restatement's batch: each is one transaction rewriting its rows (and their entries in the store's index), then a
# step of the job's progress, so a learn's progress moves every few seconds on a large model.
RESTATE_BATCH: int = 200


def _batch(store: PostgresStore, after: int, size: int = BATCH) -> list[tuple]:
    query = store._select() + sql.SQL(" WHERE seq > %s ORDER BY seq LIMIT {}").format(sql.Literal(size))
    with store._conn.transaction(), store._conn.cursor(binary=True) as cur:
        cur.execute(query, (after,))
        return cur.fetchall()


def batches(store: PostgresStore, after: int = 0, size: int = BATCH) -> Iterator[list[tuple]]:
    """The store's rows written after sequence `after`, oldest written first, a batch at a time: each row (id,
    situation JSON, outcome, dim, glyph bits, author, ts, events, seq)."""
    while rows := _batch(store, after, size):
        yield rows
        after = rows[-1][8]


def named(store: PostgresStore, ids: list[str]) -> dict[str, list[tuple[str, str, float]]]:
    """These precedents' named outcomes: {id: [(output, value, ts)]}."""
    query = store._q("SELECT id, output, value, ts FROM {outcomes} WHERE model = %s AND id = ANY(%s) ORDER BY seq")
    out: dict[str, list[tuple[str, str, float]]] = {}
    with store._conn.transaction(), store._conn.cursor() as cur:
        for rid, output, value, ts in cur.execute(query, (store.model, ids)).fetchall():
            out.setdefault(rid, []).append((output, value, ts))
    return out


def events(blob: bytes | None, dim: int) -> list | None:
    return kernel._events_from_blob(None if blob is None else bytes(blob), dim)


def restate_rest(
    store: PostgresStore, model: glyphh_spec.Model, progress: Callable[[float, int], None], held: Container[str]
) -> int:
    """Every precedent of the store but those `held` (restated by the kernel already: its sampled Space), restated
    by the model's learned spec, a RESTATE_BATCH at a time; progress(fraction, precedents seen) after each. Restating
    is idempotent (a precedent restated already comes out as it is and is not written), so a learn taken again after
    its worker died goes quickly over what was done. Returns how many changed."""
    encoder = kernel.Space(dim=store.dim, seed=model.spec.seed, lexicon=model.settings.lexicon)
    total, seen, changed = max(store.count(), 1), 0, 0
    for rows in batches(store, size=RESTATE_BATCH):
        updates = []
        for rid, text, _, dim, _, _, _, blob, _ in rows:
            if rid in held:
                continue
            old = json.loads(text)
            new = model.spec.restate(old)
            if new != old:
                glyph = encoder.encode(new, events(blob, dim))
                updates.append((rid, json.dumps(new, ensure_ascii=False), glyph))
        store.rewrite(updates)
        changed += len(updates)
        seen += len(rows)
        progress(min(seen / total, 1.0), seen)
    return changed
