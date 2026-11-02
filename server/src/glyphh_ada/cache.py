"""A worker's models, kept between messages: per (org, name) the kernel's Model over the org's PostgresStore, holding
the active spec, the learned weights and the temperatures. An entry is good while the model's version counter in Redis
(protocol.version_key) is the one it was loaded at, and for at most TTL seconds, so a lost bump costs a minute at
most. Least recently used entries go first.

A model read whole (under the kernel's exact_below precedents, or by a read that needs every precedent) holds its
precedents in memory. It is kept while the model's data counter (protocol.data_key, moved by every record, grade,
forget and job batch, on any worker) has not moved, so a burst of reads on a small model loads it once, not once per
read (2026-11-02: a burst of 50 decides on a shared CPU timed out reloading it each time). At most LOADED_MAX
precedents are held so in all; past that the least recently used loaded models go, and one larger than that alone is
never kept.

Each worker also keeps the answers of its last ANSWERS reads (decide, query, probabilities, facts), by the model's two
counters and the read's exact arguments and clearance: the kernel's reads depend on nothing else (no clock, no
randomness), so the same read of an unchanged model is answered from here.

Inline refresh (the spec's settings.refresh_every) is off in a worker: a record never learns in a request; a write
that passes a multiple of it starts a learn job instead (handlers.py)."""

import json
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
from glyphh_ada.protocol import data_key, version_key

SIZE: int = 256
TTL: float = 60.0
LOADED_MAX: int = 50_000  # precedents held in memory across the loaded models (~4 KB each at the default dimension)
ANSWERS: int = 2048


@dataclass
class Entry:
    model_id: uuid.UUID
    version: int
    stamp: str
    at: float
    model: glyphh_spec.Model
    data: str = "0"  # the model's data counter when it was loaded


class Models:
    def __init__(self, conn: psycopg.Connection, redis: Redis, size: int = SIZE, ttl: float = TTL) -> None:
        self.conn, self.redis, self.size, self.ttl = conn, redis, size, ttl
        self._lru: OrderedDict[tuple[str, str], Entry] = OrderedDict()
        self._answers: OrderedDict[str, tuple[Any, int | None]] = OrderedDict()

    def _stamps(self, org: str, name: str) -> tuple[str, str]:
        version, data = self.redis.mget([version_key(org, name), data_key(org, name)])
        return str(version or "0"), str(data or "0")

    def _live(self, schema: str, entry: Entry) -> bool:
        """The model is still there, at the version this entry holds: one lookup by its id, so a copy held in memory
        (or an answer kept) never outlives the model, nor its org (whose schema goes at once: the lookup raises
        UndefinedTable, which handlers.py answers E_MODEL_MISSING)."""
        text = "SELECT active_version FROM {s}.models WHERE id = %s AND deleted_at IS NULL"
        found = self.conn.execute(catalog.q(schema, text), (entry.model_id,)).fetchone()
        return found is not None and found[0] == entry.version

    def get(self, org: str, schema: str, name: str) -> Entry:
        (stamp, data), key = self._stamps(org, name), (org, name)
        hit = self._lru.get(key)
        fresh = hit is not None and hit.stamp == stamp and time.monotonic() - hit.at < self.ttl
        if hit is not None and fresh and (hit.data == data or not hit.model.space.loaded) and self._live(schema, hit):
            hit.data = data
            self._lru.move_to_end(key)
            return hit
        self._lru.pop(key, None)
        found = catalog.active(self.conn, schema, name)
        if found is None:
            raise model_missing(name)
        entry = self.load(schema, found, stamp)
        entry.data = data
        self._lru[key] = entry
        while len(self._lru) > self.size:
            self._lru.popitem(last=False)
        return entry

    def load(self, schema: str, found: catalog.Live, stamp: str = "0") -> Entry:
        """A Model over the active version's store, opened as a worker opens it: no index made, no precedent
        loaded, no inline refresh."""
        spec = glyphh_spec.Spec.from_json(found.spec)
        # Opened read-only, the store only checks the model is there: no DDL and no lock on the org's schema (its
        # partition and index were made with the model); then made writable, for this worker's writes to it.
        store = PostgresStore(self.conn, schema, found.store, dim=spec.dimension, readonly=True)
        store.readonly = False
        model = glyphh_spec.Model(spec, store=store)
        model.refresh_every = None
        return Entry(found.id, found.version, stamp, time.monotonic(), model)

    def drop_org(self, org: str) -> None:
        """Every model of this org out of the cache (its schema went: the org was deleted)."""
        for key in [k for k in self._lru if k[0] == org]:
            del self._lru[key]

    def settle(self, org: str, name: str, entry: Entry) -> None:
        """After a read: a model read whole is kept while what it holds fits LOADED_MAX with the others loaded; the
        least recently used loaded models go first, and one alone past it goes at once."""
        if not entry.model.space.loaded:
            return
        if len(entry.model.space) > LOADED_MAX:
            self._lru.pop((org, name), None)
            return
        held = sum(len(e.model.space) for e in self._lru.values() if e.model.space.loaded)
        for key in [k for k, e in self._lru.items() if e.model.space.loaded and k != (org, name)]:
            if held <= LOADED_MAX:
                break
            held -= len(self._lru.pop(key).model.space)

    def bump(self, org: str, name: str) -> None:
        """Every worker's copy of this model is stale from now: the counter moves, this one's entry goes."""
        self.redis.incr(version_key(org, name))
        self._lru.pop((org, name), None)

    def unload(self, org: str, name: str) -> None:
        """This worker's copy of the model goes if it holds the precedents in memory."""
        entry = self._lru.get((org, name))
        if entry is not None and entry.model.space.loaded:
            del self._lru[(org, name)]

    def changed(self, org: str, name: str) -> None:
        """The model's precedents changed: every worker's copy read whole is stale from now."""
        self.redis.incr(data_key(org, name))

    @staticmethod
    def _key(org: str, name: str, entry: Entry, op: str, args: dict[str, Any], clearance: float) -> str:
        what = json.dumps([op, args, clearance], sort_keys=True, separators=(",", ":"), default=str)
        return f"{org}\x00{name}\x00{entry.stamp}\x00{entry.data}\x00{what}"

    def answer(
        self, org: str, name: str, entry: Entry, op: str, args: dict[str, Any], clearance: float
    ) -> tuple[Any, int | None] | None:
        """This read's answer, when this worker gave it for the model as it stands now."""
        key = self._key(org, name, entry, op, args, clearance)
        found = self._answers.get(key)
        if found is not None:
            self._answers.move_to_end(key)
        return found

    def keep(
        self, org: str, name: str, entry: Entry, op: str, args: dict[str, Any], clearance: float, answer: Any
    ) -> None:
        self._answers[self._key(org, name, entry, op, args, clearance)] = (answer, entry.version)
        while len(self._answers) > ANSWERS:
            self._answers.popitem(last=False)
