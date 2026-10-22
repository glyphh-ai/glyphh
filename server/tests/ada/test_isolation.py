"""Two orgs, one service: neither can read or write the other's models, precedents or jobs, through its key, through a
worker's message, or through the database itself, where every table of an org's schema fails closed."""

import uuid

import httpx
import psycopg
import pytest
from psycopg import sql
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import pg
from glyphh_ada.errors import Refusal
from glyphh_ada.handlers import handle
from glyphh_ada.process import Worker
from glyphh_ada.protocol import Message
from tests.ada.conftest import a_model, an_org, shape
from tests.conftest import DATABASE_URL


def _tables(conn: psycopg.Connection, schema: str) -> list[str]:
    found = conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = %s AND c.relkind IN ('r', 'p') ORDER BY 1",
        (schema,),
    )
    return [r[0] for r in found.fetchall()]


def _rows(conn: psycopg.Connection, schema: str, table: str) -> int:
    return int(conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(schema, table))).fetchone()[0])


async def test_an_org_never_sees_anothers_models_or_precedents(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _alice, a_key = await an_org(engine, ada)
    bob, b_key = await an_org(engine, ada)
    await a_model(ada, a_key, n=30)
    await a_model(ada, a_key, "only-alice", n=2)
    await a_model(ada, b_key)
    bobs = (await ada.get("/v1/models", headers=b_key)).json()["models"]
    assert [(m["name"], m["precedents"]) for m in bobs] == [("shapes", 0)]
    asked = (await ada.post("/v1/models/shapes/query", json={"data": shape(1)}, headers=b_key)).json()
    assert asked["receipts"] == [] and not asked["sufficient"]
    nothing = await ada.post("/v1/models/only-alice/query", json={"data": shape(1)}, headers=b_key)
    assert (nothing.status_code, nothing.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    written = await ada.post("/v1/models/only-alice/record", json={"data": shape(1)}, headers=b_key)
    assert written.status_code == 404
    job = (await ada.post("/v1/models/shapes/calibrate", headers=a_key)).json()
    assert (await ada.get(f"/v1/jobs/{job['id']}", headers=b_key)).status_code == 404
    assert (await ada.get(f"/v1/jobs/{job['id']}", headers=a_key)).status_code == 200
    with pytest.raises(Refusal, match="No model named only-alice"):  # a worker's message for bob's org
        handle(worker.ctx, Message(str(bob.org_id), "only-alice", "query", {"data": shape(1)}))
    alices = (await ada.get("/v1/models/shapes", headers=a_key)).json()
    assert alices["precedents"] == 30


async def test_every_table_of_an_org_schema_fails_closed(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    alice, a_key = await an_org(engine, ada)
    bob, b_key = await an_org(engine, ada)
    await a_model(ada, a_key, n=10)
    await a_model(ada, b_key, n=1)
    schema = pg.schema_for(str(alice.org_id))
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:  # the server's own role
        tables = _tables(conn, schema)
        assert {"models", "spec_versions", "jobs", "requests", "precedents", "outcomes", "meta", "counts"} <= set(
            tables
        )
        assert any(t.startswith("p_") for t in tables)  # the model's partition, fenced too
        fenced = conn.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_policies p"
            " ON p.schemaname = n.nspname AND p.tablename = c.relname AND p.policyname = 'tenant'"
            " WHERE n.nspname = %s AND c.relrowsecurity AND c.relforcerowsecurity",
            (schema,),
        ).fetchone()[0]
        assert fenced == len(tables)
        for org in ("", str(bob.org_id), str(uuid.uuid4())):  # no org, another org, an org that is no one
            conn.execute("SELECT set_config('glyphh.org_id', %s, false)", (org,))
            assert {t: _rows(conn, schema, t) for t in tables} == dict.fromkeys(tables, 0)
            updated = conn.execute(sql.SQL("UPDATE {} SET n = 0").format(sql.Identifier(schema, "counts")))
            assert updated.rowcount == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match="row-level security"):
                conn.execute(
                    sql.SQL("INSERT INTO {} (id, name, created_by) VALUES (%s, 'x', 'eve')").format(
                        sql.Identifier(schema, "models")
                    ),
                    (uuid.uuid4(),),
                )
        pg.enter(conn, str(alice.org_id))
        assert _rows(conn, schema, "precedents") == 10 and _rows(conn, schema, "models") == 1


async def test_clearance_is_the_keys_or_less_never_more(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, full = await an_org(engine, ada)
    await a_model(ada, full, n=20)
    low = (await ada.post("/v1/keys", json={"name": "low", "clearance": 0.5}, headers=who.headers)).json()
    low_key = {"authorization": f"Bearer {low['key']}"}

    async def tree(key: dict[str, str], clearance: float | None = None) -> dict:
        body = {"data": shape(3), "top": 1, **({"clearance": clearance} if clearance is not None else {})}
        return (await ada.post("/v1/models/shapes/facts", json=body, headers=key)).json()[0]["tree"]

    assert "secret" in str(await tree(full))
    assert "secret" not in str(await tree(full, 0.5))
    assert "secret" not in str(await tree(low_key))
    assert "secret" not in str(await tree(low_key, 1.0))  # asking for more than the key's is the key's
