"""A worker's one Postgres connection (psycopg 3, sync, autocommit: the kernel's store opens its own transactions, and
savepoints inside a caller's), and the org it acts for. Every message sets its org for the session before anything
is read: `glyphh.org_id`, which the org schema's row-level security checks (orgschema.py), and a search_path of the
org's schema then public (every statement names its schema anyway)."""

import re
import uuid

import psycopg

_DRIVER = re.compile(r"^postgres(ql)?(\+\w+)?://")


def libpq_url(url: str) -> str:
    """The server's SQLAlchemy URL (postgresql+asyncpg://…?ssl=…) as libpq takes it (postgresql://…?sslmode=…)."""
    url = _DRIVER.sub("postgresql://", url)
    return url.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(libpq_url(url), autocommit=True)


def schema_for(org: str) -> str:
    """An org's schema, from its database id alone (never from a caller's input): ada_<id without dashes>."""
    return "ada_" + uuid.UUID(org).hex


def org_of(schema: str) -> str:
    return str(uuid.UUID(schema.removeprefix("ada_")))


def enter(conn: psycopg.Connection, org: str) -> str:
    """From here until the next enter, this connection acts for this org only. Returns its schema."""
    schema = schema_for(org)
    conn.execute(
        "SELECT set_config('glyphh.org_id', %s, false), set_config('search_path', %s, false)",
        (org, f'"{schema}", public'),  # public too: pgvector's operators (<~>, bit_hamming_ops) live there
    )
    return schema
