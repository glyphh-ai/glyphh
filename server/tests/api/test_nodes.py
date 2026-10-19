"""The key and the nodes on the runtime's own calls: the heartbeat's new fields (rrotor's clusters) kept per node and
answered with the org's newest key beside the licence; every welcome carrying the key; a hello naming its node; and
the org's runtime nodes counted against the plan, softly."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import LicenseRecord, Node, Rrotor
from glyphh_server.ops import license_keys
from tests.api.test_heartbeat import beat, send
from tests.api.test_self_hosted import made, rt
from tests.connector import granted, tool
from tests.db.helpers import Person, person
from tests.link import WAIT, connect, hello, hosted_runtime, local_runtime, runtime_row, self_runtime, server

CLUSTER = uuid.uuid4()


async def a_key(engine: AsyncEngine, who: Person) -> str:
    async with engine.begin() as conn:
        key = await license_keys.issue(conn, Ed25519PrivateKey.generate(), who.org_id, datetime(2027, 3, 1, tzinfo=UTC))
    assert key is not None
    return key


async def nodes_of(engine: AsyncEngine, runtime_id: uuid.UUID) -> list[Any]:
    async with engine.connect() as conn:
        found = select(Node).where(Node.rrotor_id == runtime_id).order_by(Node.node_id)
        return list(await conn.execute(found))


async def test_a_heartbeat_names_its_node_and_is_answered_with_the_key(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    runtime = rt(await made(client, ada))
    assert (await send(client, runtime.token, beat())).json()["license_key"] is None  # no key yet, nothing new said
    assert await nodes_of(engine, runtime.id) == []
    key = await a_key(engine, ada)
    for node, role, held in (("rrotor-0", "head", 1_200), ("rrotor-1", "follower", 1_200), ("rrotor-0", "head", 1_300)):
        said = beat(node_id=node, cluster_id=str(CLUSTER), role=role, precedents=held)
        res = await send(client, runtime.token, said)
        assert res.status_code == 200 and res.json()["license_key"] == key and res.json()["licence"]["payload"]
    kept = [(n.node_id, n.cluster_id, n.role, n.precedents, n.version) for n in await nodes_of(engine, runtime.id)]
    assert kept == [("rrotor-0", CLUSTER, "head", 1_300, "2.1.0"), ("rrotor-1", CLUSTER, "follower", 1_200, "2.1.0")]
    row = await runtime_row(engine, runtime.id)
    assert row.precedents == 1_300 and row.precedents_at is not None


@pytest.mark.parametrize(
    "over",
    [{"role": "leader"}, {"node_id": "two words"}, {"node_id": ""}, {"precedents": -1}, {"cluster_id": "x"}],
)
async def test_the_new_fields_are_checked(client: httpx.AsyncClient, engine: AsyncEngine, over: dict[str, Any]) -> None:
    runtime = rt(await made(client, await person(engine)))
    assert (await send(client, runtime.token, beat(**({"node_id": "n1"} | over)))).status_code == 422


async def test_every_welcome_carries_the_key_and_a_hello_names_its_node(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    key = await a_key(engine, ada)
    for runtime in (await local_runtime(engine, ada), await hosted_runtime(engine, ada)):
        said = hello(runtime, node_id="pod-a", cluster_id=str(CLUSTER), role="head")
        async with server() as srv, connect(srv, runtime.token) as ws:
            await ws.send_json(said)
            welcome = await ws.receive_json(timeout=WAIT)
        assert welcome["license_key"] == key and (welcome["licence"] is None) == (runtime.mode == "local")
        kept = await nodes_of(engine, runtime.id)
        assert [(n.node_id, n.cluster_id, n.role, n.precedents, n.version) for n in kept] == [
            ("pod-a", CLUSTER, "head", None, "1.2.3")
        ]


async def _self(engine: AsyncEngine, who: Person, host: str, **values: Any) -> uuid.UUID:
    runtime = await self_runtime(engine, who, f"https://{host}.acme.test")
    if values:
        async with engine.begin() as conn:
            await conn.execute(update(Rrotor).where(Rrotor.id == runtime.id).values(**values))
    return runtime.id


async def test_the_orgs_nodes_are_counted_softly_against_the_plan(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Free")
    now = datetime.now(UTC)
    hosted = await hosted_runtime(engine, ada, "box")  # never linked: a hosted machine is a node all the same
    online = await _self(engine, ada, "on", state="online", last_seen_at=now)
    clustered = await _self(engine, ada, "cl", last_heartbeat_at=now - timedelta(hours=1))
    await _self(engine, ada, "gone", state="offline", last_seen_at=now - timedelta(days=3))  # not heard: not counted
    await _self(engine, ada, "never")  # never seen: not counted
    stale = await _self(engine, ada, "st", last_heartbeat_at=now - timedelta(hours=2))
    await local_runtime(engine, ada)  # a local runtime is not a runtime node
    async with engine.begin() as conn:
        for runtime_id, node, seen in (
            (clustered, "b", now),
            (clustered, "a", now),
            (clustered, "old", now - timedelta(days=5)),
            (stale, "old", now - timedelta(days=5)),
        ):
            await conn.execute(Node.__table__.insert().values(rrotor_id=runtime_id, node_id=node, seen_at=seen))
    res = await client.get("/v1/license/nodes", headers=ada.headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["count"], body["max_nodes"], body["over"]) == (5, 1, True)
    shown = [(n["runtime_id"], n["node_id"], n["mode"]) for n in body["nodes"]]
    assert sorted(shown, key=str) == sorted(
        [
            (str(clustered), "a", "self"),
            (str(clustered), "b", "self"),
            (str(hosted.id), None, "hosted"),
            (str(online), None, "self"),
            (str(stale), None, "self"),
        ],
        key=str,
    )
    assert [n for n in shown if n[0] == str(clustered)] == [
        (str(clustered), "a", "self"),
        (str(clustered), "b", "self"),
    ]
    seen = {n["runtime_id"]: n["seen_at"] for n in body["nodes"]}
    assert seen[str(hosted.id)] is None and seen[str(online)] is not None
    _, auth = await granted(engine, ada)
    used = (await tool(client, auth, "usage"))["content"][0]["text"]
    assert used.startswith("Runtime nodes: 5 of 1 (over the plan: shown, never stopped).\n")
    enterprise = await person(engine, "Enterprise")
    await hosted_runtime(engine, enterprise)
    unlimited = (await client.get("/v1/license/nodes", headers=enterprise.headers)).json()
    assert (unlimited["count"], unlimited["max_nodes"], unlimited["over"]) == (1, None, False)
    assert (await client.get("/v1/license/nodes")).status_code == 401


async def test_another_orgs_keys_and_nodes_are_not_seen(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    await a_key(engine, ada)
    runtime = rt(await made(client, ada))
    await send(client, runtime.token, beat(node_id="n1"))
    async with engine.begin() as conn:
        await tenancy.enter(conn, eve.org_id)
        assert (await conn.execute(select(func.count()).select_from(LicenseRecord))).scalar_one() == 0
        assert (await conn.execute(select(func.count()).select_from(Node))).scalar_one() == 0
        assert await license_keys.newest(conn, ada.org_id) is None
