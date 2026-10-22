"""Restating a model's store after learning changed what a case carries (its learned word weights or pairs): every
precedent the job did not hold in memory, read in batches by its sequence, passed through the learned spec's restate
and encoded again as the kernel's Space.rewrite does, then written back a batch at a time."""

import json
from collections.abc import Callable

import glyphh_kernel as kernel
import glyphh_spec
from glyphh_postgres import PostgresStore
from psycopg import sql

BATCH: int = 1000


def _batch(store: PostgresStore, after: int) -> list[tuple]:
    query = store._select() + sql.SQL(" WHERE seq > %s ORDER BY seq LIMIT {}").format(sql.Literal(BATCH))
    with store._conn.transaction(), store._conn.cursor(binary=True) as cur:
        cur.execute(query, (after,))
        return cur.fetchall()


def restate_rest(store: PostgresStore, model: glyphh_spec.Model, progress: Callable[[float], None]) -> int:
    """Every precedent of the store that the model's (sampled) Space does not hold, restated. Returns how many
    changed."""
    held = model.space._at
    encoder = kernel.Space(dim=store.dim, seed=model.spec.seed, lexicon=model.settings.lexicon)
    total, seen, changed, after = max(store.count(), 1), 0, 0, 0
    while rows := _batch(store, after):
        updates = []
        for rid, text, _, dim, _, _, _, events, _ in rows:
            if rid in held:
                continue
            old = json.loads(text)
            new = model.spec.restate(old)
            if new != old:
                glyph = encoder.encode(new, kernel._events_from_blob(None if events is None else bytes(events), dim))
                updates.append((rid, json.dumps(new, ensure_ascii=False), glyph))
        store.rewrite(updates)
        changed += len(updates)
        seen += len(rows)
        after = rows[-1][8]
        progress(min(seen / total, 1.0))
    return changed
