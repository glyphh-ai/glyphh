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
from glyphh_server.models import Rrotor, Run
from glyphh_server.ops import hosted
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.fly import Fly
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, person
from tests.fakes import FakeFly, fake_http
from tests.link import a_model, hosted_runtime

FLY_SETTINGS = PROVIDER_SETTINGS.model_copy(
    update={"fly_api_token": "fly_test_token", "fly_app": "glyphh-runtimes", "fly_image": "registry.fly.io/r:1"}
)


async def _row(engine: AsyncEngine, runtime_id: str) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(select(Rrotor).where(Rrotor.id == uuid.UUID(runtime_id)))).one()


async def test_a_pro_persons_runtime_is_made_on_first_start_then_started_stopped_shown_and_destroyed(
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
        assert (view["state"], view["region"], view["seconds_used"], view["hours_allowed"]) == (
            "stopped",
            "iad",
            0,
            none["hours_allowed"],
        )
        row = await _row(engine, view["runtime_id"])
        assert (row.mode, row.fly_machine_id, row.fly_volume_id, row.install_id) == ("hosted", "m_1", "vol_1", None)
        assert [c[:2] for c in fly.calls] == [
            ("POST", "/volumes"),
            ("POST", "/machines"),
            ("POST", "/machines/m_1/start"),
        ]
        machine = fly.machines["m_1"]
        env = machine["config"]["env"]
        assert (machine["config"]["image"], machine["config"]["mounts"], machine["skip_launch"]) == (
            "registry.fly.io/r:1",
            [{"volume": "vol_1", "path": "/data"}],
            True,
        )
        assert (env["RROTOR_MODE"], env["RROTOR_SERVER"], env["RROTOR_RUNTIME_ID"]) == (
            "hosted",
            FLY_SETTINGS.base_url,
            view["runtime_id"],
        )
        assert hash_secret(env["RROTOR_RUNTIME_TOKEN"]) == row.token_hash and machine["state"] == "started"
        again = await client.post("/v1/runtime/start", headers=ada.headers)
        assert again.json()["runtime_id"] == view["runtime_id"] and len(fly.machines) == 1
        assert fly.calls[-1][:2] == ("POST", "/machines/m_1/start")
        async with engine.begin() as conn:  # linked, and ran this month and last
            await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(state="online"))
            _, v1, _ = await a_model(engine, ada)
            now = datetime.now(UTC)
            for started, seconds in ((now - timedelta(minutes=1), 90), (now - timedelta(days=40), 500)):
                values = {"model_version_id": v1, "rrotor_id": row.id, "function": "start", "caller": "test"}
                await conn.execute(insert(Run).values(**values, status="done", started_at=started, seconds=seconds))
        starts = [c[1] for c in fly.calls].count("/machines/m_1/start")
        online = await client.post("/v1/runtime/start", headers=ada.headers)
        assert online.json()["state"] == "online"
        assert [c[1] for c in fly.calls].count("/machines/m_1/start") == starts == 2  # online: not started again
        shown = (await client.get("/v1/runtime", headers=ada.headers)).json()
        assert (shown["state"], shown["seconds_used"]) == ("online", 90)
        stopped = await client.post("/v1/runtime/stop", headers=ada.headers)
        assert stopped.json()["state"] == "stopped" and fly.machines["m_1"]["state"] == "stopped"
        assert (await client.delete("/v1/runtime", headers=ada.headers)).status_code == 204
        assert fly.machines == {} and fly.volumes == {}
        assert (await client.get("/v1/runtime", headers=ada.headers)).json()["state"] == "none"
        for path in ("/v1/runtime/stop", "/v1/runtime"):
            res = await client.request("POST" if path.endswith("stop") else "DELETE", path, headers=ada.headers)
            assert (res.status_code, res.json()["error"]["reason"]) == (404, "no_runtime")


async def test_hosting_needs_the_plan_the_server_set_up_and_fly_answering(engine: AsyncEngine) -> None:
    free, pro = await person(engine), await person(engine, "Pro")
    fly = FakeFly()
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        res = await client.post("/v1/runtime/start", headers=free.headers)
        assert (res.status_code, res.json()["error"]["reason"]) == (403, "not_on_plan")
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
    rt = await hosted_runtime(engine, who)
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
    found = {r[0] for r in await hosted.idle_hosted(engine, timedelta(minutes=10))}
    assert found == {idle_id, down}
    del fly.machines["m_down"]  # Fly lost it: stopping fails, is logged, the rest go on
    client = Fly(fake_http(fly=fly), FLY_SETTINGS)
    assert await hosted.stop_idle(engine, client, timedelta(minutes=10)) == 1
    assert fly.machines["m_idle"]["state"] == "stopped" and fly.machines["m_busy"]["state"] == "started"
    assert (await _row(engine, str(idle_id))).state == "stopped" and (await _row(engine, str(down))).state == "online"
    assert await hosted.stop_idle(engine, client, timedelta(minutes=10)) == 0


async def test_the_waker_starts_a_machine_that_is_not_online(engine: AsyncEngine) -> None:
    fly = FakeFly()
    fly.machines["m_1"] = {"id": "m_1", "state": "stopped"}
    ada = await person(engine, "Pro")
    runtime_id = await _hosted(engine, ada, "offline", datetime.now(UTC), "m_1")
    wake = hosted.waker(engine, Fly(fake_http(fly=fly), FLY_SETTINGS))
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

    async def stop_idle(engine: AsyncEngine, fly: Fly, idle: timedelta) -> int:
        ticks.append(1)
        if len(ticks) == 1:
            raise RuntimeError("fly hiccup")
        stopped.set()
        return 0

    monkeypatch.setattr(hosted, "stop_idle", stop_idle)
    app = create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))
    async for _ in _client(app):
        assert app.state.hub.waker is not None
        await asyncio.wait_for(stopped.wait(), 5)
    assert "stopping idle runtimes failed" in caplog.text and len(ticks) >= 2
