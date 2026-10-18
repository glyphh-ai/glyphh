"""Hosted runtimes: made on Fly the first time a Pro or Team person starts theirs (a volume, a machine with the
runtime token in its environment), started and stopped, shown with the month's run time, destroyed; idle ones
stopped by the server; refusals when hosting is off, Fly fails, or the plan has none."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import app as app_module
from glyphh_server.app import create_app
from glyphh_server.errors import Conflict, Unavailable
from glyphh_server.models import Rrotor, Run, RuntimeKey
from glyphh_server.ops import tend as tending
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.idle import idle_hosted, stop_idle, waker
from glyphh_server.ops.runtime_keys import key_hash
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, person
from tests.fakes import FakeFly, fake_http
from tests.link import a_model, holding, hosted_runtime

FLY_SETTINGS = PROVIDER_SETTINGS.model_copy(
    update={"fly_api_token": "fly_test_token", "fly_app": "glyphh-runtimes", "fly_image": "registry.fly.io/r:1"}
)


async def _row(engine: AsyncEngine, runtime_id: str) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(select(Rrotor).where(Rrotor.id == uuid.UUID(runtime_id)))).one()


async def test_a_persons_runtime_is_made_on_first_start_then_started_stopped_shown_and_destroyed(
    engine: AsyncEngine,
) -> None:
    fly = FakeFly()
    ada = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        res = await client.get("/v1/runtime", headers=ada.headers)
        assert res.status_code == 200, res.text
        none = res.json()
        assert none == {**none, "runtime_id": None, "state": "none", "seconds_used": 0}
        res = await client.post("/v1/runtime/start", headers=ada.headers)
        assert res.status_code == 200, res.text
        view = res.json()
        assert (view["state"], view["region"], view["seconds_used"]) == ("stopped", "iad", 0)
        assert "paused" not in view and "hours_allowed" not in view
        row = await _row(engine, view["runtime_id"])
        assert (row.mode, row.fly_machine_id, row.fly_volume_id, row.install_id) == ("hosted", "m_2", "vol_1", None)
        assert view["address"] == "https://m_2.glyphh.app"
        assert [c[:2] for c in fly.calls] == [
            ("GET", "/machines"),
            ("POST", "/machines"),  # the doorman, made with the first runtime
            ("POST", "/machines/m_1/start"),
            ("POST", "/volumes"),
            ("POST", "/machines"),
            ("POST", "/machines/m_2/start"),
        ]
        doorman = fly.machines["m_1"]
        assert (doorman["name"], doorman["config"]["env"], doorman["config"]["services"][0]["autostop"]) == (
            "doorman",
            {"RROTOR_MODE": "doorman", "RROTOR_PUBLIC_DOMAIN": "glyphh.app"},
            "off",
        )
        assert "mounts" not in doorman["config"] and doorman["config"]["guest"]["memory_mb"] == 256
        machine = fly.machines["m_2"]
        env = machine["config"]["env"]
        assert (machine["config"]["image"], machine["config"]["mounts"], machine["skip_launch"]) == (
            "registry.fly.io/r:1",
            [{"volume": "vol_1", "path": "/data"}],
            True,
        )
        service = machine["config"]["services"][0]
        assert (service["internal_port"], service["autostart"], service["autostop"]) == (7777, True, "stop")
        assert (env["RROTOR_MODE"], env["RROTOR_SERVER"], env["RROTOR_RUNTIME_ID"], env["RROTOR_PUBLIC_DOMAIN"]) == (
            "hosted",
            FLY_SETTINGS.base_url,
            view["runtime_id"],
            "glyphh.app",
        )
        assert hash_secret(env["RROTOR_RUNTIME_TOKEN"]) == row.token_hash and machine["state"] == "started"
        again = await client.post("/v1/runtime/start", headers=ada.headers)
        assert again.json()["runtime_id"] == view["runtime_id"] and len(fly.machines) == 2
        assert (
            fly.calls[-1][:2] == ("POST", "/machines/m_2/start") and [c[1] for c in fly.calls].count("/machines") == 3
        )
        async with engine.begin() as conn:  # linked, with a tally of this month and a stale one
            values = {"state": "online", "month": datetime.now(UTC).strftime("%Y-%m"), "month_seconds": 90}
            await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(**values))
        starts = [c[1] for c in fly.calls].count("/machines/m_2/start")
        online = await client.post("/v1/runtime/start", headers=ada.headers)
        assert online.json()["state"] == "online"
        assert [c[1] for c in fly.calls].count("/machines/m_2/start") == starts == 2  # online: not started again
        shown = (await client.get("/v1/runtime", headers=ada.headers)).json()
        assert (shown["state"], shown["seconds_used"]) == ("online", 90)
        async with engine.begin() as conn:
            await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(month="2020-01"))
        assert (await client.get("/v1/runtime", headers=ada.headers)).json()["seconds_used"] == 0  # another month's
        stopped = await client.post("/v1/runtime/stop", headers=ada.headers)
        assert stopped.json()["state"] == "stopped" and fly.machines["m_2"]["state"] == "stopped"
        assert (await client.delete("/v1/runtime", headers=ada.headers)).status_code == 204
        assert list(fly.machines) == ["m_1"] and fly.volumes == {}
        assert (await client.get("/v1/runtime", headers=ada.headers)).json()["state"] == "none"
        for path in ("/v1/runtime/stop", "/v1/runtime"):
            res = await client.request("POST" if path.endswith("stop") else "DELETE", path, headers=ada.headers)
            assert (res.status_code, res.json()["error"]["reason"]) == (404, "no_runtime")


async def test_hosting_needs_the_server_set_up_and_fly_answering(engine: AsyncEngine) -> None:
    pro = await person(engine, "Pro")
    fly = FakeFly()
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        fly.fail = True
        res = await client.post("/v1/runtime/start", headers=pro.headers)
        error = res.json()["error"]
        assert (res.status_code, error["reason"], error["status"]) == (503, "fly_failed", 500)
        assert (await client.get("/v1/runtime", headers=pro.headers)).json()["state"] == "none"  # rolled back
    async for client in _client(create_app(PROVIDER_SETTINGS, http=fake_http())):
        res = await client.post("/v1/runtime/start", headers=pro.headers)
        assert (res.status_code, res.json()["error"]["reason"]) == (503, "hosting_off")
    with pytest.raises(Unavailable, match="Hosting isn't set up"):
        Fly(fake_http(), PROVIDER_SETTINGS)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(Unavailable) as refused:
        await Fly(httpx.AsyncClient(transport=httpx.MockTransport(down)), FLY_SETTINGS).state("m_1")
    assert refused.value.detail == {"reason": "fly_failed", "error": "ConnectError"}
    fly.fail = False
    fly.machines["m_1"] = {"id": "m_1", "state": "started"}
    assert await Fly(fake_http(fly=fly), FLY_SETTINGS).state("m_1") == "started"
    with pytest.raises(Unavailable) as refused:
        await Fly(fake_http(fly=fly), FLY_SETTINGS).state("m_9")
    assert refused.value.detail["status"] == 404
    await Fly(fake_http(fly=fly), FLY_SETTINGS).destroy("m_1", None)  # a machine that never got its volume
    assert fly.machines == {} and fly.calls[-1][:2] == ("DELETE", "/machines/m_1")


async def _hosted(engine: AsyncEngine, who: Person, state: str, seen: datetime, machine: str) -> uuid.UUID:
    rt = await hosted_runtime(engine, who, machine)
    async with engine.begin() as conn:
        values = {"state": state, "last_seen_at": seen, "fly_machine_id": machine}
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(**values))
    return rt.id


async def test_idle_runtimes_are_stopped_busy_recent_and_stopped_ones_left(engine: AsyncEngine) -> None:
    fly = FakeFly()
    for name in ("m_idle", "m_busy", "m_recent", "m_down"):
        fly.machines[name] = {"id": name, "state": "started"}
    now = datetime.now(UTC)
    idle, busy, recent, fresh, off = [await person(engine, "Pro") for _ in range(5)]
    long_ago = now - timedelta(hours=1)
    idle_id = await _hosted(engine, idle, "online", long_ago, "m_idle")
    busy_id = await _hosted(engine, busy, "online", long_ago, "m_busy")
    recent_id = await _hosted(engine, recent, "online", long_ago, "m_recent")
    await _hosted(engine, fresh, "online", now, "m_fresh")
    await _hosted(engine, off, "stopped", long_ago, "m_off")
    down = await _hosted(engine, await person(engine, "Pro"), "online", long_ago, "m_down")
    async with engine.begin() as conn:
        for who, runtime_id, status, ended in (
            (busy, busy_id, "needs_input", None),
            (recent, recent_id, "done", now - timedelta(minutes=2)),
            (idle, idle_id, "done", long_ago),
        ):
            _, v1, _ = await a_model(engine, who)
            values = {"model_version_id": v1, "rrotor_id": runtime_id, "function": "start", "caller": "test"}
            await conn.execute(insert(Run).values(**values, status=status, started_at=long_ago, ended_at=ended))
    found = {r[0] for r in await idle_hosted(engine, timedelta(minutes=10))}
    assert found == {idle_id, down}
    del fly.machines["m_down"]  # Fly lost it: stopping fails, is logged, the rest go on
    client = Fly(fake_http(fly=fly), FLY_SETTINGS)
    assert await stop_idle(engine, client, timedelta(minutes=10)) == 1
    assert fly.machines["m_idle"]["state"] == "stopped" and fly.machines["m_busy"]["state"] == "started"
    assert (await _row(engine, str(idle_id))).state == "stopped" and (await _row(engine, str(down))).state == "online"
    assert await stop_idle(engine, client, timedelta(minutes=10)) == 0


async def test_the_waker_starts_a_machine_that_is_not_online(engine: AsyncEngine) -> None:
    fly = FakeFly()
    fly.machines["m_1"] = {"id": "m_1", "state": "stopped"}
    ada = await person(engine, "Pro")
    runtime_id = await _hosted(engine, ada, "offline", datetime.now(UTC), "m_1")
    wake = waker(engine, Fly(fake_http(fly=fly), FLY_SETTINGS))
    await wake(runtime_id)
    assert fly.machines["m_1"]["state"] == "started"
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(state="online"))
    await wake(runtime_id)
    assert [c[1] for c in fly.calls].count("/machines/m_1/start") == 1
    with pytest.raises(Conflict):
        await wake(uuid.uuid4())


async def test_the_app_stops_idle_runtimes_every_minute_and_survives_a_failure(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(app_module, "IDLE_EVERY", 0.01)
    ticks: list[int] = []
    stopped = asyncio.Event()

    async def tend(engine: AsyncEngine, fly: Fly, hub: Any, idle: timedelta, step: int, stripe: Any) -> None:
        assert stripe is not None and stripe.meter == "glyphh_hosting"
        ticks.append(step)
        if len(ticks) == 1:
            raise RuntimeError("fly hiccup")
        stopped.set()

    monkeypatch.setattr(tending, "tend", tend)
    app = create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))
    async for _ in _client(app):
        assert app.state.hub.waker is not None
        await asyncio.wait_for(stopped.wait(), 5)
    assert "tending hosted runtimes failed" in caplog.text and len(ticks) >= 2


async def test_runtime_keys_are_made_shown_once_pushed_down_the_link_and_revoked(
    engine: AsyncEngine, redis: Any
) -> None:
    fly = FakeFly()
    fly.machines["m_0"] = {"id": "m_0", "name": "other", "state": "stopped"}  # not the doorman: looked past
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        runtime_id = (await client.post("/v1/runtime/start", headers=ada.headers)).json()["runtime_id"]
        made = await client.post(
            "/v1/runtime/keys", json={"name": " Claude ", "expires_in_days": 30}, headers=ada.headers
        )
        assert made.status_code == 201, made.text
        key = made.json()
        assert key["key"].startswith("glyphh_rk_") and key["name"] == "Claude" and key["revoked_at"] is None
        async with engine.connect() as conn:
            row = (await conn.execute(select(RuntimeKey).where(RuntimeKey.id == uuid.UUID(key["id"])))).one()
        assert row.key_hash == key_hash(key["key"]) and row.rrotor_id is None  # every hosted machine of hers
        assert key["runtime_id"] is None
        async with holding(redis, uuid.UUID(runtime_id)) as sent:
            second = (
                await client.post(
                    "/v1/runtime/keys", json={"name": "the CRM", "expires_in_days": 90}, headers=ada.headers
                )
            ).json()
            pushed = await sent()
            assert (pushed["type"], pushed["hashes"]) == ("keys", [row.key_hash, key_hash(second["key"])])
            gone = await client.delete(f"/v1/runtime/keys/{key['id']}", headers=ada.headers)
            assert gone.status_code == 200 and gone.json()["revoked_at"] is not None
            assert (await sent())["hashes"] == [key_hash(second["key"])]
        listed = (await client.get("/v1/runtime/keys", headers=ada.headers)).json()
        assert [(k["name"], k["revoked_at"] is None) for k in listed] == [("Claude", False), ("the CRM", True)]
        assert "key" not in listed[0]
        again = await client.delete(f"/v1/runtime/keys/{key['id']}", headers=ada.headers)
        assert again.status_code == 404
        theirs = await client.delete(f"/v1/runtime/keys/{second['id']}", headers=eve.headers)
        assert theirs.status_code == 404
        assert (await client.get("/v1/runtime/keys", headers=eve.headers)).json() == []
        eves = (await client.post("/v1/runtime/start", headers=eve.headers)).json()
        assert (
            eves["address"] != f"https://{runtime_id}"
            and [m["name"] for m in fly.machines.values()].count("doorman") == 1
        )


async def test_the_tally_counts_online_time_starts_again_with_the_month_and_never_pauses(
    engine: AsyncEngine, redis: Any
) -> None:
    from glyphh_server.ops.link.hub import Hub

    pro, team = await person(engine, "Pro"), await person(engine, "Team")
    now = datetime.now(UTC)
    month = now.strftime("%Y-%m")
    online = await _hosted(engine, pro, "online", now, "m_on")
    turned = await _hosted(engine, team, "online", now, "m_turned")
    stopped = await _hosted(engine, team, "stopped", now, "m_off")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == online).values(month=month, month_seconds=10**7))
        await conn.execute(update(Rrotor).where(Rrotor.id == turned).values(month="2020-01", month_seconds=10**6))
    await tending.tally(engine, 60, "iad")
    rows = [await _row(engine, str(i)) for i in (online, turned, stopped)]
    assert [(r.month, r.month_seconds, r.state) for r in rows] == [
        (month, 10**7 + 60, "online"),  # far past any hours there were: never paused
        (month, 60, "online"),
        (month, 0, "stopped"),
    ]
    fly = FakeFly()
    await tending.tend(engine, Fly(fake_http(fly=fly), FLY_SETTINGS), Hub(redis), timedelta(minutes=10), 60)
    assert (await _row(engine, str(online))).month_seconds == 10**7 + 120
    meter = StripeClient(fake_http(), "sk_test", "glyphh_hosting")  # with Stripe, the hosting due is reported too
    await tending.tend(engine, Fly(fake_http(fly=fly), FLY_SETTINGS), Hub(redis), timedelta(minutes=10), 60, meter)
