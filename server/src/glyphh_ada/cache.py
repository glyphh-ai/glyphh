"""A worker's models, kept between messages: per (org, name) the kernel's Model over the org's PostgresStore, holding
the active spec, the learned weights and the temperatures, never the precedents (Postgres's own cache holds the hot
partitions). An entry is good while the model's version counter in Redis (protocol.version_key) is the one it was
loaded at, and for at most TTL seconds, so a lost bump costs a minute at most. Least recently used entries go first.

Inline refresh (the spec's settings.refresh_every) is off in a worker: a record never learns in a request."""

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore
from redis import Redis

from glyphh_ada import catalog
from glyphh_ada.errors import model_missing
from glyphh_ada.protocol import version_key

SIZE: int = 256
TTL: float = 60.0


@dataclass
class Entry:
    model_id: uuid.UUID
    version: int
    stamp: str
    at: float
    model: glyphh_spec.Model


class Models:
    def __init__(self, conn: psycopg.Connection, redis: Redis, size: int = SIZE, ttl: float = TTL) -> None:
        self.conn, self.redis, self.size, self.ttl = conn, redis, size, ttl
        self._lru: OrderedDict[tuple[str, str], Entry] = OrderedDict()

    def _stamp(self, org: str, name: str) -> str:
        return str(self.redis.get(version_key(org, name)) or "0")

    def get(self, org: str, schema: str, name: str) -> Entry:
        stamp, key = self._stamp(org, name), (org, name)
        hit = self._lru.get(key)
        if hit is not None and hit.stamp == stamp and time.monotonic() - hit.at < self.ttl:
            self._lru.move_to_end(key)
            return hit
        self._lru.pop(key, None)
        found = catalog.active(self.conn, schema, name)
        if found is None:
            raise model_missing(name)
        entry = self.load(schema, found, stamp)
        self._lru[key] = entry
        while len(self._lru) > self.size:
            self._lru.popitem(last=False)
        return entry

    def load(self, schema: str, found: tuple[uuid.UUID, int, Any, Any], stamp: str = "0") -> Entry:
        """A Model over the store, opened as a worker opens it: no index made, no precedent loaded, no inline
        refresh."""
        model_id, version, spec_json, _ = found
        spec = glyphh_spec.Spec.from_json(spec_json)
        # Opened read-only, the store only checks the model is there: no DDL and no lock on the org's schema (its
        # partition and index were made with the model); then made writable, for this worker's writes to it.
        store = PostgresStore(self.conn, schema, model_id.hex, dim=spec.dimension, readonly=True)
        store.readonly = False
        model = glyphh_spec.Model(spec, store=store)
        model.refresh_every = None
        return Entry(model_id, version, stamp, time.monotonic(), model)

    def settle(self, org: str, name: str, entry: Entry) -> None:
        """After a read: a model read whole (under exact_below precedents) holds its precedents in memory now, which
        other workers' writes would leave stale, so its entry goes; the next message opens it afresh."""
        if entry.model.space.loaded:
            self._lru.pop((org, name), None)

    def bump(self, org: str, name: str) -> None:
        """Every worker's copy of this model is stale from now: the counter moves, this one's entry goes."""
        self.redis.incr(version_key(org, name))
        self._lru.pop((org, name), None)
