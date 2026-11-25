"""The kernel's suite on either store. By default every Space(path=...) is a SQLite file, as ever. With
GLYPHH_TEST_POSTGRES set to a connection string (a Postgres with pgvector), every path a test opens is a model in
PostgresStore instead (one schema for the run, a model per path), so the same tests run on Postgres; tests about
the SQLite file itself (its bytes, its migrations, read-only folders) are marked sqlite_only and skipped there."""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest

POSTGRES = os.environ.get("GLYPHH_TEST_POSTGRES")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "sqlite_only: about the SQLite file itself; skipped on PostgresStore")
    config.addinivalue_line("markers", "postgres: needs GLYPHH_TEST_POSTGRES")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if POSTGRES and item.get_closest_marker("sqlite_only"):
            item.add_marker(pytest.mark.skip(reason="about the SQLite file; the run is on PostgresStore"))
        if not POSTGRES and item.get_closest_marker("postgres"):
            item.add_marker(pytest.mark.skip(reason="GLYPHH_TEST_POSTGRES is not set"))


@pytest.fixture(scope="session")
def pg_schema() -> str:
    """A fresh schema for this run (dropped at the end)."""
    import psycopg

    schema = f"kt_{uuid.uuid4().hex[:12]}"
    yield schema
    with psycopg.connect(POSTGRES, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture(autouse=True, scope="session")
def _stores_on_postgres(request: pytest.FixtureRequest) -> None:
    if not POSTGRES:
        yield
        return
    import psycopg

    import glyphh_kernel
    import glyphh_postgres

    schema = request.getfixturevalue("pg_schema")
    conn = psycopg.connect(POSTGRES, autocommit=True)
    original = glyphh_kernel._store_for

    def store_for(path: str, readonly: bool, dim: int) -> glyphh_kernel.Store:
        model = hashlib.sha256(str(path).encode()).hexdigest()[:16]
        if readonly:
            try:
                return glyphh_postgres.PostgresStore(conn, schema, model, dim=dim, readonly=True)
            except ValueError:  # nothing written there yet: an empty store, as a file not yet made reads
                return glyphh_postgres.PostgresStore(conn, schema, model, dim=dim)
        return glyphh_postgres.PostgresStore(conn, schema, model, dim=dim)

    glyphh_kernel._store_for = store_for
    yield
    glyphh_kernel._store_for = original
    conn.close()
