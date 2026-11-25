"""A model's store as a job reads it to learn and calibrate: its newest limits.JOB_SAMPLE precedents, not all of them
(a fully loaded 1M-precedent model needs about 16 GB). Everything else, the writes of learned weights and
temperatures included, goes to the store itself. A model this size or smaller is read whole: the job then learns and
calibrates exactly as the kernel does anywhere."""

from typing import Any

from glyphh_postgres import PostgresStore
from psycopg import sql


class Sampled:
    def __init__(self, store: PostgresStore, size: int) -> None:
        self.store, self.size = store, size
        self._ids: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def rows(self, by_time: bool = True) -> list[Any]:
        """The newest `size` precedents, oldest first (as the kernel loads a store)."""
        s = self.store
        newest = s._select() + sql.SQL(" ORDER BY ts DESC, seq DESC LIMIT {}").format(sql.Literal(self.size))
        with s._conn.transaction(), s._conn.cursor(binary=True) as cur:
            cur.execute(newest)
            found = cur.fetchall()
        found.reverse()
        self._ids = [r[0] for r in found]
        return [s._stored(r) for r in found]

    def named(self) -> list[tuple[str, str, str, float]]:
        s = self.store
        query = s._q("SELECT id, output, value, ts FROM {outcomes} WHERE model = %s AND id = ANY(%s) ORDER BY ts, seq")
        with s._conn.transaction(), s._conn.cursor() as cur:
            cur.execute(query, (s.model, self._ids))
            return cur.fetchall()
