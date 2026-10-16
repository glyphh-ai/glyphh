"""schema.sql is the schema; the models map it for queries. Built from schema.sql, the database must hold exactly
the models' tables, and each the same columns, types, keys, constraints and indexes."""

from typing import Any

from sqlalchemy import Column, Connection, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Base

DIALECT = postgresql.dialect()


def _type(t: Any) -> str:
    return str(t.compile(dialect=DIALECT))


def _sql(e: Any) -> str:
    return str(e.compile(dialect=DIALECT, compile_kwargs={"literal_binds": True}))


def _keys(expressions: Any) -> tuple[str, ...]:
    """An index's columns by name, and its expressions as Postgres writes them (`lower(email)`)."""
    return tuple(e.name if isinstance(e, Column) else _sql(e) for e in expressions)


def _from_models() -> dict[str, dict[str, Any]]:
    out = {}
    for table in Base.metadata.sorted_tables:
        out[table.name] = {
            "columns": {c.name: (_type(c.type), c.nullable) for c in table.columns},
            "primary_key": sorted(c.name for c in table.primary_key.columns),
            "foreign_keys": sorted(
                (tuple(fk.parent.name for fk in fkc.elements), fkc.referred_table.name, fkc.ondelete or None)
                for fkc in table.foreign_key_constraints
            ),
            "indexes": sorted((str(ix.name), _keys(ix.expressions), bool(ix.unique)) for ix in table.indexes),
            "checks": sorted(str(c.name) for c in table.constraints if c.__class__.__name__ == "CheckConstraint"),
        }
    return out


def _from_database(conn: Connection) -> dict[str, dict[str, Any]]:
    seen = inspect(conn)
    out = {}
    for name in seen.get_table_names():
        out[name] = {
            "columns": {c["name"]: (_type(c["type"]), c["nullable"]) for c in seen.get_columns(name)},
            "primary_key": sorted(seen.get_pk_constraint(name)["constrained_columns"]),
            "foreign_keys": sorted(
                (tuple(fk["constrained_columns"]), fk["referred_table"], fk["options"].get("ondelete"))
                for fk in seen.get_foreign_keys(name)
            ),
            "indexes": sorted(
                (ix["name"], tuple(ix.get("expressions") or ix["column_names"]), bool(ix["unique"]))
                for ix in seen.get_indexes(name)
                if not ix.get("duplicates_constraint")
            ),
            "checks": sorted(c["name"] for c in seen.get_check_constraints(name)),
        }
    return out


async def test_the_models_and_schema_sql_agree(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        database = await conn.run_sync(_from_database)
    models = _from_models()
    assert sorted(database) == sorted(models)
    for table, want in models.items():
        assert database[table] == want, table
