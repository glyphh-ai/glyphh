"""Until launch there are no migrations: the schema is created, never altered. A database made by older
code would be missing columns and fail on the first request that needs one. This check refuses to boot
instead, and says how to fix it."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from glyphh_server.models import Base

FIX: str = "Until launch there are no migrations: reset the development database with `docker compose down -v`."


def missing_columns(conn: Connection) -> dict[str, list[str]]:
    seen = inspect(conn)
    missing: dict[str, list[str]] = {}
    for table in Base.metadata.sorted_tables:
        have = {c["name"] for c in seen.get_columns(table.name)}
        gone = [c.name for c in table.columns if c.name not in have]
        if gone:
            missing[table.name] = gone
    return missing


def refuse_drift(conn: Connection) -> None:
    missing = missing_columns(conn)
    if missing:
        raise RuntimeError(f"The database is behind the code: missing columns {missing}. {FIX}")
