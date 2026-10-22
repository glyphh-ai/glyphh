"""An org's models, in its schema (worker side): made from a JSON spec (checked by the kernel, then against the cloud's
bounds), listed, read and deleted. A model's precedents live in the kernel's store under the model's id (hex), a
partition of their own with its HNSW index (glyphh_postgres.PostgresStore); its name is the caller's handle. Every
statement names the org's schema: public has tables of the same names (the server's own `models`)."""

import json
import uuid
from typing import Any

import glyphh_spec
import psycopg
from glyphh_postgres import PostgresStore
from psycopg import sql
from psycopg.types.json import Jsonb

from glyphh_ada import limits, orgschema
from glyphh_ada.errors import Refusal, model_missing

_ACTIVE = """
    SELECT m.id, m.active_version, v.spec, m.created_at FROM {s}.models m
    JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version
    WHERE m.name = %s AND m.deleted_at IS NULL
"""
_LIST = """
    SELECT m.name, m.id, m.active_version, coalesce(c.n, 0), m.created_at FROM {s}.models m
    LEFT JOIN {s}.counts c ON c.model = replace(m.id::text, '-', '')
    WHERE m.deleted_at IS NULL ORDER BY m.name
"""


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


def active(conn: psycopg.Connection, schema: str, name: str) -> tuple[uuid.UUID, int, Any, Any] | None:
    """(id, active version, spec JSON, made at) of the org's live model by this name; None when there is none."""
    if not has(conn, schema, "counts"):  # no model was ever made: no schema, or the kernel's tables not yet
        return None
    found = conn.execute(q(schema, _ACTIVE), (name,)).fetchone()
    return None if found is None else (found[0], found[1], found[2], found[3])


def store(conn: psycopg.Connection, schema: str, model_id: uuid.UUID, dim: int, index: bool = False) -> PostgresStore:
    return PostgresStore(conn, schema, model_id.hex, dim=dim, index=index)


def listing(conn: psycopg.Connection, schema: str) -> list[dict[str, Any]]:
    if not has(conn, schema, "counts"):
        return []
    rows = conn.execute(q(schema, _LIST)).fetchall()
    keys = ("name", "id", "version", "precedents", "created_at")
    return [dict(zip(keys, r, strict=True)) for r in rows]


def view(conn: psycopg.Connection, schema: str, name: str) -> dict[str, Any]:
    found = active(conn, schema, name)
    if found is None:
        raise model_missing(name)
    model_id, version, spec, made = found
    held = conn.execute(q(schema, "SELECT n FROM {s}.counts WHERE model = %s"), (model_id.hex,)).fetchone()
    count = held[0] if held else 0
    return {"name": name, "id": model_id, "version": version, "precedents": count, "created_at": made, "spec": spec}


def create(conn: psycopg.Connection, org: str, name: str, spec_json: Any, author: str) -> dict[str, Any]:
    spec = parse(spec_json)
    schema = orgschema.ensure(conn, org)
    model_id = uuid.uuid4()
    insert = "INSERT INTO {s}.spec_versions (model_id, version, spec, note, made_by) VALUES (%s, 1, %s, 'made', %s)"
    try:
        with conn.transaction():
            conn.execute(
                q(schema, "INSERT INTO {s}.models (id, name, created_by) VALUES (%s, %s, %s)"), (model_id, name, author)
            )
            conn.execute(q(schema, insert), (model_id, Jsonb(spec_json), author))
            store(conn, schema, model_id, spec.dimension, index=True)  # its partition and HNSW index
            orgschema.fence(conn, schema, org)
    except psycopg.errors.UniqueViolation:
        raise Refusal("E_CONFLICT", f"This org has a model named {name} already.", 409, model=name) from None
    return view(conn, schema, name)


def delete(conn: psycopg.Connection, schema: str, name: str) -> uuid.UUID:
    """The model gone: its partition, outcomes, learned meta and count; its row kept, marked deleted."""
    found = active(conn, schema, name)
    if found is None:
        raise model_missing(name)
    model_id, _, spec, _ = found
    with conn.transaction():
        conn.execute(q(schema, "UPDATE {s}.models SET deleted_at = now() WHERE id = %s"), (model_id,))
        store(conn, schema, model_id, glyphh_spec.Spec.from_json(spec).dimension).drop()
    return model_id
