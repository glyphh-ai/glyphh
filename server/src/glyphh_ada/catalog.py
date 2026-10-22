"""An org's models, in its schema (worker side): made from a JSON spec (checked by the kernel, then against the cloud's
bounds), listed, read and deleted. A model's precedents live in the kernel's store under a key of their own, a
partition with its HNSW index (glyphh_postgres.PostgresStore): the model's id (hex) for its first version, and a new
key for each version a re-encode made (versions.py); the active version names the store it reads. Its name is the
caller's handle. Every statement names the org's schema: public has tables of the same names (the server's own
`models`)."""

import hashlib
import json
import uuid
from typing import Any, NamedTuple

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore
from psycopg import sql
from psycopg.types.json import Jsonb

from glyphh_ada import limits, orgschema
from glyphh_ada.errors import Refusal, model_missing

_ACTIVE = """
    SELECT m.id, m.active_version, v.spec, m.created_at, v.store FROM {s}.models m
    JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version
    WHERE m.name = %s AND m.deleted_at IS NULL
"""
_LIVE = """
    FROM {s}.models m JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version
    LEFT JOIN {s}.counts c ON c.model = v.store WHERE m.deleted_at IS NULL
"""
_LIST = "SELECT m.name, m.id, m.active_version, coalesce(c.n, 0), m.created_at" + _LIVE + " ORDER BY m.name"
_TOTAL = "SELECT coalesce(sum(c.n), 0)" + _LIVE
# An index on a partition's ids alone. The kernel finds a precedent by `id` (grade, forget, has, rewrite), and its
# partition's primary key is (model, id), whose leading column such a lookup does not give: without this each is a
# scan of the whole index (51,000 cost units at a million precedents: a learn rewriting 50,000 glyphs ran for hours).
BY_ID = "CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} (id)"


class Live(NamedTuple):
    """A live model: its id, active version, that version's spec (JSON), when it was made, the store it reads."""

    id: uuid.UUID
    version: int
    spec: Any
    made: Any
    store: str


def q(schema: str, text: str) -> sql.Composed:
    """A statement with {s} as the org's schema."""
    return sql.SQL(text).format(s=sql.Identifier(schema))  # type: ignore[arg-type]


def parse(spec_json: Any) -> glyphh_spec.Spec:
    """The kernel's own check of the spec (E_SPEC naming where), then the cloud's bounds (E_SPEC_LIMIT)."""
    if len(json.dumps(spec_json)) > limits.SPEC_BYTES_MAX:
        raise Refusal("E_SPEC_LIMIT", f"A spec is at most {limits.SPEC_BYTES_MAX} bytes of JSON.", 413)
    try:
        spec = glyphh_spec.Spec.from_json(spec_json)
    except glyphh_spec.SpecError as e:
        raise Refusal("E_SPEC", str(e), 422, path=e.path) from None
    limits.check_spec(spec)
    return spec


def has(conn: psycopg.Connection, schema: str, table: str) -> bool:
    found = conn.execute("SELECT to_regclass(%s)", (f'"{schema}".{table}',)).fetchone()
    return found is not None and found[0] is not None


def active(conn: psycopg.Connection, schema: str, name: str) -> Live | None:
    """The org's live model by this name; None when there is none."""
    if not has(conn, schema, "counts"):  # no model was ever made: no schema, or the kernel's tables not yet
        return None
    found = conn.execute(q(schema, _ACTIVE), (name,)).fetchone()
    return None if found is None else Live(*found)


def live(conn: psycopg.Connection, schema: str, name: str) -> Live:
    found = active(conn, schema, name)
    if found is None:
        raise model_missing(name)
    return found


def store(conn: psycopg.Connection, schema: str, key: str, dim: int, index: bool = False) -> PostgresStore:
    """The kernel's store under this key (made, with its partition and the partition's id index, when it is not
    there yet)."""
    made = PostgresStore(conn, schema, key, dim=dim, index=index)
    part = _part(key)
    conn.execute(sql.SQL(BY_ID).format(sql.Identifier(part + "_id"), sql.Identifier(schema, part)))
    return made


def _part(key: str) -> str:
    """A store's partition, as glyphh_postgres names it."""
    return "p_" + hashlib.sha256(key.encode()).hexdigest()[:24]


def drop_store(conn: psycopg.Connection, schema: str, key: str) -> None:
    """A store gone, as PostgresStore.drop does it, whether or not its partition was ever made."""
    part = _part(key)
    with conn.transaction():
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(schema, part)))
        for table in ("outcomes", "meta", "counts"):
            conn.execute(sql.SQL("DELETE FROM {} WHERE model = %s").format(sql.Identifier(schema, table)), (key,))


def total(conn: psycopg.Connection, schema: str) -> int:
    """The precedents the org holds, its live models' active stores together (what its plan's cap counts)."""
    return int(conn.execute(q(schema, _TOTAL)).fetchone()[0])  # type: ignore[index]


def listing(conn: psycopg.Connection, schema: str) -> list[dict[str, Any]]:
    if not has(conn, schema, "counts"):
        return []
    rows = conn.execute(q(schema, _LIST)).fetchall()
    keys = ("name", "id", "version", "precedents", "created_at")
    return [dict(zip(keys, r, strict=True)) for r in rows]


def count(conn: psycopg.Connection, schema: str, key: str) -> int:
    """The precedents a store holds."""
    held = conn.execute(q(schema, "SELECT n FROM {s}.counts WHERE model = %s"), (key,)).fetchone()
    return int(held[0]) if held else 0


def view(conn: psycopg.Connection, schema: str, name: str) -> dict[str, Any]:
    found = live(conn, schema, name)
    return {
        "name": name,
        "id": found.id,
        "version": found.version,
        "precedents": count(conn, schema, found.store),
        "created_at": found.made,
        "spec": found.spec,
    }


def create(conn: psycopg.Connection, org: str, name: str, spec_json: Any, author: str) -> dict[str, Any]:
    spec = parse(spec_json)
    schema = orgschema.ensure(conn, org)
    model_id = uuid.uuid4()
    insert = (
        "INSERT INTO {s}.spec_versions (model_id, version, spec, note, made_by, store)"
        " VALUES (%s, 1, %s, 'made', %s, %s)"
    )
    try:
        with conn.transaction():
            conn.execute(
                q(schema, "INSERT INTO {s}.models (id, name, created_by) VALUES (%s, %s, %s)"), (model_id, name, author)
            )
            conn.execute(q(schema, insert), (model_id, Jsonb(spec_json), author, model_id.hex))
            store(conn, schema, model_id.hex, spec.dimension, index=True)  # its partition and HNSW index
            orgschema.fence(conn, schema, org)
    except psycopg.errors.UniqueViolation:
        raise Refusal("E_CONFLICT", f"This org has a model named {name} already.", 409, model=name) from None
    return view(conn, schema, name)


def delete(conn: psycopg.Connection, schema: str, name: str) -> uuid.UUID:
    """The model gone from the live store at once: every store its versions read (partitions, outcomes, learned
    meta, counts), its versions, its jobs and their files; its row kept, marked deleted."""
    found = live(conn, schema, name)
    with conn.transaction():
        conn.execute(q(schema, "UPDATE {s}.models SET deleted_at = now() WHERE id = %s"), (found.id,))
        stores = q(schema, "SELECT DISTINCT store FROM {s}.spec_versions WHERE model_id = %s")
        for (key,) in conn.execute(stores, (found.id,)).fetchall():
            drop_store(conn, schema, key)
        jobs = "DELETE FROM {s}.files WHERE id IN (SELECT id FROM {s}.jobs WHERE model_id = %s)"
        conn.execute(q(schema, jobs), (found.id,))
        for table in ("jobs", "spec_versions"):
            conn.execute(q(schema, f"DELETE FROM {{s}}.{table} WHERE model_id = %s"), (found.id,))
    return found.id
