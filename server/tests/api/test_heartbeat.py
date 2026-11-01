"""A self-hosted runtime's heartbeat (`POST /v1/license/verify`, its runtime token as auth): exactly its four fields,
answered with a fresh licence carrying its grace; only what it says is kept. And an offline licence for an
air-gapped one, as one token, 1 to 365 days, on Enterprise only."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_self_hosted import made, rt, verifies
from tests.db.helpers import person
from tests.link import local_runtime, runtime_row

MACHINE = "ab" * 32


def beat(**over: Any) -> dict[str, Any]:
    return {"machine": MACHINE, "licence_id": None, "version": "2.1.0", "active_runs": 3, **over}


async def send(client: httpx.AsyncClient, token: str | None, body: dict[str, Any]) -> httpx.Response:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return await client.post("/v1/license/verify", json=body, headers=headers)


async def test_a_heartbeat_is_answered_with_a_licence_and_keeps_only_what_it_says(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    runtime = rt(await made(client, ada))
    res = await send(client, runtime.token, beat())
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store", res.text
    licence = res.json()["licence"]
    verifies((await client.get("/v1/license/key", headers=ada.headers)).json(), licence)
    p = licence["payload"]
    assert (p["kind"], p["grace_days"], p["runtime_id"], p["install_id"]) == ("heartbeat", 14, str(runtime.id), None)
    assert p["mods"] == {"ada": {"limits": {"precedents": None}}}  # self-hosted: unlimited
    left = datetime.fromisoformat(p["expires_at"]) - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < left <= timedelta(hours=24)
    row = await runtime_row(engine, runtime.id)
    assert (row.image_version, row.active_runs, row.machine_hash, row.state) == ("2.1.0", 3, MACHINE, "stopped")
    assert row.last_heartbeat_at is not None and row.last_seen_at is None
    again = (await send(client, runtime.token, beat(licence_id=p["licence_id"], active_runs=0))).json()["licence"]
    assert again["payload"]["licence_id"] != p["licence_id"]
    listed = (await client.get("/v1/runtimes/self", headers=ada.headers)).json()[0]
    assert listed["version"] == "2.1.0" and listed["last_heartbeat_at"]


@pytest.mark.parametrize(
    "body",
    [
        beat(ip="10.0.0.1"),
        {k: v for k, v in beat().items() if k != "licence_id"},
        beat(machine="not-a-hash"),
        beat(active_runs=-1),
        beat(version=""),
        beat(licence_id="nope"),
    ],
)
async def test_the_body_is_exactly_its_four_fields(
    client: httpx.AsyncClient, engine: AsyncEngine, body: dict[str, Any]
) -> None:
    runtime = rt(await made(client, await person(engine)))
    assert (await send(client, runtime.token, body)).status_code == 422


async def test_only_a_self_hosted_runtimes_own_token_beats(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    for token in (None, "not-a-token"):
        res = await send(client, token, beat())
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"
    res = await send(client, (await local_runtime(engine, ada)).token, beat())
    assert res.status_code == 403 and res.json()["error"]["reason"] == "not_self"


def decoded(token: str) -> dict[str, Any]:
    return json.loads(base64.urlsafe_b64decode(token))


async def test_an_offline_licence_is_one_token_good_for_the_days_asked(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine, "Enterprise"), await person(engine)
    runtime = rt(await made(client, ada))
    path = f"/v1/runtimes/{runtime.id}/offline-licence"
    res = await client.post(path, json={"days": 365}, headers=ada.headers)
    assert res.status_code == 200, res.text
    body = res.json()
    licence = decoded(body["token"])
    assert sorted(licence) == ["payload", "signature"]
    verifies((await client.get("/v1/license/key", headers=ada.headers)).json(), licence)
    p = licence["payload"]
    assert (p["kind"], p["grace_days"], p["runtime_id"], p["plan"]) == ("offline", 14, str(runtime.id), "Enterprise")
    assert uuid.UUID(p["licence_id"]) and p["expires_at"] == body["expires_at"]
    left = datetime.fromisoformat(body["expires_at"]) - datetime.now(UTC)
    assert timedelta(days=364, hours=23) < left <= timedelta(days=365)
    for days in (0, 366, None):
        assert (await client.post(path, json={"days": days}, headers=ada.headers)).status_code == 422
    assert (await client.post(path, json={"days": 30}, headers=eve.headers)).status_code == 404
    local = await local_runtime(engine, ada)
    res = await client.post(f"/v1/runtimes/{local.id}/offline-licence", json={"days": 30}, headers=ada.headers)
    assert res.status_code == 404
    assert (await client.post(path, json={"days": 30})).status_code == 401


async def test_an_offline_licence_is_not_in_any_plan_but_enterprise(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    for plan in ("Free", "Pro", "Team"):
        ada = await person(engine, plan)
        runtime = rt(await made(client, ada))
        res = await client.post(f"/v1/runtimes/{runtime.id}/offline-licence", json={"days": 30}, headers=ada.headers)
        error = res.json()["error"]
        assert (res.status_code, error["code"], error["reason"]) == (403, "E_NOT_IN_PLAN", "offline"), plan
        assert "sales@glyphh.ai" in error["message"]
        assert (await send(client, runtime.token, beat())).status_code == 200  # heartbeats on every plan
