"""
PostgresStore: a model's precedents in Postgres, for Ada Cloud. psycopg 3 and pgvector; beside glyphh_kernel.py.

One schema per org (given at construction, never from a caller's input), holding:

    precedents  model, id, situation jsonb, outcome, dim, glyph bit varying, author, ts, events, seq;
                PRIMARY KEY (model, id); PARTITION BY LIST (model), a partition per model, each with an HNSW
                index on its glyphs as bit(dim) (bit_hamming_ops)
    outcomes    model, id, output, value, ts, seq (a precedent's named outcomes)
    meta        model, key, value jsonb (learned weights, temperatures, settings, the encoding)
    counts      model, n (precedents held, kept by every write in the same transaction)

A glyph is the kernel's bipolar vector packed as bits (+1 as 1): 512 bytes at dim 4096 against 4 KB as int8, and
sim(a, b) = 1 - 2 * hamming(a, b) / dim, which pgvector's <~> computes. shortlist(glyph, size) asks the model's
partition for the `size` nearest glyphs by Hamming distance through its index; a Space opened with load=False
re-ranks them by its own exact weighted score (glyphh_kernel.Space.candidates).

    store = PostgresStore("postgresql://...", schema="ada_9f2c...", model="tickets")
    model = glyphh_spec.Model(spec, store=store)          # reads shortlist once the model is big
    space = glyphh_kernel.Space(store=store)              # every precedent loaded, as from a file

Every method is its own transaction (a savepoint inside a caller's): put_many is one, whatever its size.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

import glyphh_kernel as kernel
from glyphh_kernel import DEFAULT, ENCODING, ReadOnlyError, Row, StoredRow

try:
    import psycopg
    from psycopg import sql
    from psycopg.adapt import Dumper, Loader
    from psycopg.pq import Format
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - the kernel without its Postgres extra
    psycopg = None  # type: ignore[assignment]

_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
EF_SEARCH_MAX = 1000  # pgvector's ceiling on hnsw.ef_search; a larger shortlist scans on (iterative_scan)
HNSW_M, HNSW_EF_CONSTRUCTION = 64, 400  # the index's graph: see PostgresStore


def pack(glyph: np.ndarray) -> bytes:
    """A bipolar glyph as bits, +1 as 1, most significant bit first (Postgres's bit order)."""
    return np.packbits(np.asarray(glyph) > 0).tobytes()


def unpack(data: bytes, dim: int) -> np.ndarray:
    """Bits back to the bipolar int8 glyph."""
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))[:dim]
    return bits.astype(np.int8) * 2 - 1


def bit_sim(a: np.ndarray, b: np.ndarray) -> float:
    """sim() through the bits: 1 - 2 * hamming / dim, the same number as the kernel's for bipolar glyphs."""
    hamming = int(np.count_nonzero((np.asarray(a) > 0) != (np.asarray(b) > 0)))
    return 1.0 - 2.0 * hamming / len(a)


class Bits:
    """A glyph packed for Postgres as bit varying (binary)."""

    __slots__ = ("data", "n")

    def __init__(self, data: bytes, n: int):
        self.data, self.n = data, n

    @classmethod
    def of(cls, glyph: np.ndarray) -> Bits:
        return cls(pack(glyph), len(glyph))

    def glyph(self) -> np.ndarray:
        return unpack(self.data, self.n)


if psycopg is not None:

    class _BitsDumper(Dumper):
        format = Format.BINARY
        oid = psycopg.postgres.types["varbit"].oid

        def dump(self, obj: Bits) -> bytes:
            return struct.pack("!i", obj.n) + obj.data

    class _BitsLoader(Loader):
        format = Format.BINARY

        def load(self, data: Any) -> Bits:
            raw = bytes(data)
            return Bits(raw[4:], struct.unpack("!i", raw[:4])[0])


class PostgresStore:
    """One model's precedents in an org's schema (see the module). conninfo: a psycopg connection string, or a
    connection (the store then never closes it, and runs inside the caller's transaction when there is one).
    dim: the model's dimension (the partition's index is on bit(dim)). index=False makes no HNSW index (an import
    builds it once at the end: build_index). ef_search: pgvector's hnsw.ef_search for a shortlist (default: the
    shortlist's size, at least 40, at most 1000). hnsw_m and ef_construction: the index's graph (pgvector's m and
    ef_construction), when this store makes it. pgvector's defaults (16, 64) lose most of the exact top for a
    query that gives few of the roles its records carry (bench/shortlist.py: 49% at 100k precedents, against
    99.7% at 64 and 400); the defaults here are those."""

    def __init__(
        self,
        conninfo: Any,
        schema: str,
        model: str,
        *,
        dim: int = kernel.DIM,
        readonly: bool = False,
        index: bool = True,
        ef_search: int | None = None,
        hnsw_m: int = HNSW_M,
        ef_construction: int = HNSW_EF_CONSTRUCTION,
    ):
        if psycopg is None:
            raise ImportError("PostgresStore needs psycopg 3: pip install 'glyphh-kernel[postgres]'")
        if not isinstance(schema, str) or not _SCHEMA.match(schema):
            raise ValueError("a schema is 1-63 lower-case letters, digits and _, not starting with a digit")
        if not isinstance(model, str) or not 0 < len(model) <= 200:
            raise ValueError("a model is named by 1 to 200 characters")
        if isinstance(dim, bool) or not isinstance(dim, int) or not 1 <= dim <= 64000:
            raise ValueError("dim is an integer from 1 to 64000 (pgvector's bit index)")
        self.schema, self.model, self.dim = schema, model, dim
        self.readonly = bool(readonly)
        self.ef_search = ef_search
        self.hnsw_m, self.ef_construction = int(hnsw_m), int(ef_construction)
        self.path = None  # no file: Space reads its errors' location from here
        self.name = f"{schema}/{model}"
        self._owned = isinstance(conninfo, str)
        self._conn = psycopg.connect(conninfo, autocommit=True) if self._owned else conninfo
        self._conn.adapters.register_dumper(Bits, _BitsDumper)
        self._conn.adapters.register_loader("varbit", _BitsLoader)
        self._conn.adapters.register_loader("bit", _BitsLoader)
        part = "p_" + hashlib.sha256(model.encode()).hexdigest()[:24]
        s = sql.Identifier(schema)
        self._t = {
            "schema": s,
            "precedents": sql.SQL("{}.precedents").format(s),
            "part": sql.SQL("{}.{}").format(s, sql.Identifier(part)),
            "part_name": sql.Identifier(part),
            "index": sql.Identifier(f"{part}_glyph"),
            "outcomes": sql.SQL("{}.outcomes").format(s),
            "meta": sql.SQL("{}.meta").format(s),
            "counts": sql.SQL("{}.counts").format(s),
            "pseq": sql.SQL("{}.precedent_seq").format(s),
            "oseq": sql.SQL("{}.outcome_seq").format(s),
        }
        if self.readonly:
            if not self._exists():
                raise ValueError(f"no model {model!r} in schema {schema!r} to read")
        else:
            self._setup(index)

    # -- setup ---------------------------------------------------------

    def _q(self, text: str) -> sql.Composed:
        return sql.SQL(text).format(**{k: v for k, v in self._t.items()})

    def _exists(self) -> bool:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f'"{self.schema}".counts',))
            if not cur.fetchone()[0]:
                return False
            cur.execute(self._q("SELECT 1 FROM {counts} WHERE model = %s"), (self.model,))
            return cur.fetchone() is not None

    def _setup(self, index: bool) -> None:
        """The org's schema, its tables and this model's partition (with its index), made once; concurrent
        workers making the same wait on an advisory lock."""
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"glyphh:{self.schema}",))
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            if cur.fetchone() is None:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(self._q("CREATE SCHEMA IF NOT EXISTS {schema}"))
            cur.execute(self._q("CREATE SEQUENCE IF NOT EXISTS {pseq}"))
            cur.execute(self._q("CREATE SEQUENCE IF NOT EXISTS {oseq}"))
            cur.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {precedents} ("
                    " model text NOT NULL, id text NOT NULL, situation jsonb NOT NULL,"
                    " outcome text NOT NULL DEFAULT '', dim integer NOT NULL, glyph bit varying NOT NULL,"
                    " author text NOT NULL DEFAULT 'anon', ts double precision NOT NULL DEFAULT 0, events bytea,"
                    " seq bigint NOT NULL DEFAULT nextval({pseq_text}::regclass),"
                    " writes integer NOT NULL DEFAULT 1,"  # 1 when a write made the row, more when it replaced
                    " PRIMARY KEY (model, id)) PARTITION BY LIST (model)"
                ).format(precedents=self._t["precedents"], pseq_text=sql.Literal(f'"{self.schema}".precedent_seq'))
            )
            cur.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {outcomes} ("
                    " model text NOT NULL, id text NOT NULL, output text NOT NULL, value text NOT NULL,"
                    " ts double precision NOT NULL DEFAULT 0,"
                    " seq bigint NOT NULL DEFAULT nextval({oseq_text}::regclass),"
                    " PRIMARY KEY (model, id, output))"
                ).format(outcomes=self._t["outcomes"], oseq_text=sql.Literal(f'"{self.schema}".outcome_seq'))
            )
            cur.execute(
                self._q("CREATE TABLE IF NOT EXISTS {meta} (model text NOT NULL, key text NOT NULL, value jsonb NOT NULL, PRIMARY KEY (model, key))")
            )
            cur.execute(self._q("CREATE TABLE IF NOT EXISTS {counts} (model text PRIMARY KEY, n bigint NOT NULL DEFAULT 0)"))
            cur.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {part} PARTITION OF {precedents} FOR VALUES IN ({model})").format(
                    part=self._t["part"], precedents=self._t["precedents"], model=sql.Literal(self.model)
                )
            )
            if index:
                self._create_index(cur)
            cur.execute(self._q("INSERT INTO {counts} (model, n) VALUES (%s, 0) ON CONFLICT (model) DO NOTHING"), (self.model,))
            cur.execute(self._q("SELECT 1 FROM {meta} WHERE model = %s AND key = 'encoding'"), (self.model,))
            if cur.fetchone() is None:
                cur.execute(self._q("SELECT n FROM {counts} WHERE model = %s"), (self.model,))
                held = cur.fetchone()[0]
                cur.execute(
                    self._q("INSERT INTO {meta} (model, key, value) VALUES (%s, 'encoding', %s)"),
                    (self.model, Jsonb(ENCODING if held == 0 else 1)),
                )

    def _create_index(self, cur: Any) -> None:
        cur.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {part} USING hnsw ((glyph::bit({dim})) bit_hamming_ops)").format(
                index=self._t["index"], part=self._t["part"], dim=sql.Literal(self.dim)
            )
            + sql.SQL(" WITH (m = {m}, ef_construction = {efc})").format(m=sql.Literal(self.hnsw_m), efc=sql.Literal(self.ef_construction))
        )

    def build_index(self) -> None:
        """The partition's HNSW index, made if it is not there (after an import: building once is far faster
        than inserting into it row by row)."""
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            self._create_index(cur)

    def drop_index(self) -> None:
        """Drop the partition's HNSW index (before a bulk import); shortlists read by a sequential scan until
        build_index."""
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(sql.SQL("DROP INDEX IF EXISTS {}.{}").format(self._t["schema"], self._t["index"]))

    def drop(self) -> None:
        """Delete the model: its partition, outcomes, meta and count."""
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("DROP TABLE IF EXISTS {part}"))
            for table in ("outcomes", "meta", "counts"):
                cur.execute(sql.SQL("DELETE FROM {} WHERE model = %s").format(self._t[table]), (self.model,))

    def _writable(self) -> None:
        if self.readonly:
            raise ReadOnlyError("write", self.name)

    # -- the Store protocol ------------------------------------------------

    def encoding(self) -> int:
        value = self.meta("encoding")
        return ENCODING if value is None else int(value)

    def reencode(self, space: kernel.Space) -> int:
        self._writable()
        updates = []
        for rid, situation, _, _, _, _, _, ev in self.rows(by_time=False):
            try:
                glyph = space.encode(json.loads(situation), kernel._events_from_blob(ev, space.dim))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            updates.append((rid, situation, glyph))
        self.rewrite(updates)
        self.set_meta("encoding", ENCODING)
        return len(updates)

    def taus(self) -> list[tuple[str, Any]]:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT key, value FROM {meta} WHERE model = %s AND (key = 'tau' OR key LIKE 'tau:%%')"), (self.model,))
            return [(k, v) for k, v in cur.fetchall()]

    def _select(self) -> sql.Composed:
        return self._q("SELECT id, situation::text, outcome, dim, glyph, author, ts, events, seq FROM {part}")

    @staticmethod
    def _stored(row: tuple) -> StoredRow:
        rid, situation, outcome, dim, glyph, author, ts, events, _ = row
        return (rid, situation, outcome, dim, glyph.glyph().tobytes(), author, ts, None if events is None else bytes(events))

    def rows(self, by_time: bool = True) -> list[StoredRow]:
        order = sql.SQL(" ORDER BY ts, seq" if by_time else " ORDER BY seq")
        with self._conn.transaction(), self._conn.cursor(binary=True) as cur:
            cur.execute(self._select() + order)
            return [self._stored(r) for r in cur]

    def named(self) -> list[tuple[str, str, str, float]]:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT id, output, value, ts FROM {outcomes} WHERE model = %s ORDER BY ts, seq"), (self.model,))
            return cur.fetchall()

    def put_many(self, rows: Sequence[tuple[Row, Sequence[tuple[str, str, float]]]]) -> None:
        self._writable()
        if not rows:
            return
        last: dict[str, Sequence[tuple[str, str, float]]] = {}
        for row, named in rows:
            if row.dim != self.dim:
                raise ValueError(f"precedent {row.id} has dim {row.dim}, the store is {self.dim}")
            last[row.id] = named
        params = [
            (self.model, row.id, row.situation, row.outcome, row.dim, Bits.of(row.glyph), row.author, row.ts, row.events)
            for row, _ in rows
        ]
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("DELETE FROM {outcomes} WHERE model = %s AND id = ANY(%s)"), (self.model, list(last)))
            cur.executemany(
                sql.SQL(
                    "INSERT INTO {precedents} (model, id, situation, outcome, dim, glyph, author, ts, events)"
                    " VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (model, id) DO UPDATE SET situation = EXCLUDED.situation,"
                    " outcome = EXCLUDED.outcome, dim = EXCLUDED.dim, glyph = EXCLUDED.glyph,"
                    " author = EXCLUDED.author, ts = EXCLUDED.ts, events = EXCLUDED.events,"
                    " seq = nextval({pseq_text}::regclass), writes = {precedents}.writes + 1"
                    " RETURNING (writes = 1)"
                ).format(precedents=self._t["precedents"], pseq_text=sql.Literal(f'"{self.schema}".precedent_seq')),
                params,
                returning=True,
            )
            added = 0
            while True:
                found = cur.fetchone()
                added += bool(found and found[0])
                if not cur.nextset():
                    break
            outcomes = [(self.model, rid, o, v, t) for rid, named in last.items() for o, v, t in named]
            if outcomes:
                cur.executemany(self._q("INSERT INTO {outcomes} (model, id, output, value, ts) VALUES (%s, %s, %s, %s, %s)"), outcomes)
            if added:
                cur.execute(self._q("UPDATE {counts} SET n = n + %s WHERE model = %s"), (added, self.model))

    def grade(self, rid: str, output: str, value: str | None, ts: float) -> None:
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            if output == DEFAULT:
                cur.execute(self._q("UPDATE {part} SET outcome = %s WHERE id = %s"), (value or "", rid))
            elif value is None:
                cur.execute(self._q("DELETE FROM {outcomes} WHERE model = %s AND id = %s AND output = %s"), (self.model, rid, output))
            else:
                cur.execute(
                    sql.SQL(
                        "INSERT INTO {outcomes} (model, id, output, value, ts) VALUES (%s, %s, %s, %s, %s)"
                        " ON CONFLICT (model, id, output) DO UPDATE SET value = EXCLUDED.value, ts = EXCLUDED.ts,"
                        " seq = nextval({oseq_text}::regclass)"
                    ).format(outcomes=self._t["outcomes"], oseq_text=sql.Literal(f'"{self.schema}".outcome_seq')),
                    (self.model, rid, output, value, ts),
                )

    def forget(self, rid: str) -> None:
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("DELETE FROM {part} WHERE id = %s"), (rid,))
            if cur.rowcount:
                cur.execute(self._q("UPDATE {counts} SET n = n - %s WHERE model = %s"), (cur.rowcount, self.model))
            cur.execute(self._q("DELETE FROM {outcomes} WHERE model = %s AND id = %s"), (self.model, rid))

    def has(self, rid: str) -> bool:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT 1 FROM {part} WHERE id = %s"), (rid,))
            return cur.fetchone() is not None

    def has_many(self, ids: Iterable[str]) -> set[str]:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT id FROM {part} WHERE id = ANY(%s)"), (list(ids),))
            return {r[0] for r in cur.fetchall()}

    def count(self) -> int:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT n FROM {counts} WHERE model = %s"), (self.model,))
            found = cur.fetchone()
            return int(found[0]) if found else 0

    def count_graded(self, output: str) -> int:
        with self._conn.transaction(), self._conn.cursor() as cur:
            if output == DEFAULT:
                cur.execute(self._q("SELECT count(*) FROM {part} WHERE outcome <> ''"))
            else:
                cur.execute(self._q("SELECT count(*) FROM {outcomes} WHERE model = %s AND output = %s"), (self.model, output))
            return int(cur.fetchone()[0])

    def set_tau(self, output: str, tau: float) -> None:
        self.set_meta("tau" if output == DEFAULT else f"tau:{output}", float(tau))

    def meta(self, key: str) -> Any:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT value FROM {meta} WHERE model = %s AND key = %s"), (self.model, key))
            found = cur.fetchone()
        # keys in the order a file gives them (sorted), whatever order jsonb keeps
        return None if found is None else json.loads(json.dumps(found[0], sort_keys=True))

    def set_meta(self, key: str, value: Any) -> None:
        self._writable()
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                self._q("INSERT INTO {meta} (model, key, value) VALUES (%s, %s, %s) ON CONFLICT (model, key) DO UPDATE SET value = EXCLUDED.value"),
                (self.model, key, Jsonb(value)),
            )

    def events(self) -> dict[str, bytes | None]:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(self._q("SELECT id, events FROM {part}"))
            return {rid: None if ev is None else bytes(ev) for rid, ev in cur.fetchall()}

    def rewrite(self, rows: Sequence[tuple[str, str, np.ndarray]]) -> None:
        self._writable()
        if not rows:
            return
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.executemany(
                self._q("UPDATE {part} SET situation = %s::jsonb, glyph = %s WHERE id = %s"),
                [(situation, Bits.of(glyph), rid) for rid, situation, glyph in rows],
            )

    def shortlist(
        self, glyph: np.ndarray, size: int, exact: bool = False
    ) -> tuple[list[StoredRow], list[tuple[str, str, str, float]]]:
        """The `size` precedents whose glyphs are nearest this one by Hamming distance (the partition's HNSW
        index, approximate; exact=True, or no index: a sequential scan, every glyph compared), oldest first, and
        their named outcomes."""
        if len(glyph) != self.dim:
            raise ValueError(f"a glyph of dim {len(glyph)}, the store is {self.dim}")
        ef = self.ef_search or max(40, size)
        with self._conn.transaction(), self._conn.cursor(binary=True) as cur:
            cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(min(ef, EF_SEARCH_MAX)),))
            if size > min(ef, EF_SEARCH_MAX):
                cur.execute("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)")
            if exact:
                cur.execute("SELECT set_config('enable_indexscan', 'off', true)")
            cur.execute(
                self._select()
                + sql.SQL(" ORDER BY glyph::bit({dim}) <~> %s::bit({dim}) LIMIT %s").format(dim=sql.Literal(self.dim)),
                (Bits.of(glyph), size),
            )
            found = sorted(cur.fetchall(), key=lambda r: (r[6], r[8]))
            ids = [r[0] for r in found]
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                self._q("SELECT id, output, value, ts FROM {outcomes} WHERE model = %s AND id = ANY(%s) ORDER BY ts, seq"),
                (self.model, ids),
            )
            named = cur.fetchall()
        return [self._stored(r) for r in found], named

    def close(self) -> None:
        if self._owned and not self._conn.closed:
            self._conn.close()
