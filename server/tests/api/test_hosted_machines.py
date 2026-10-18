"""Hosted machines: several per person up to the plan's machines, each named and of a size (Fly's guest and volume
from the one table), made and started, shown, started, stopped, restarted and deleted with its name to confirm; only
the owner's (404 for anyone else's); the routes made for one runtime acting on the first."""

import uuid
from typing import Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Rrotor
from glyphh_server.models.rrotor import SIZES, SIZES_SAID
from tests.api.test_hosted import FLY_SETTINGS
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, person
from tests.fakes import FakeFly, fake_http


async def _made(client: httpx.AsyncClient, who: Person, name: str, size: str = "small") -> dict[str, Any]:
    res = await client.post("/v1/runtimes", json={"name": name, "size": size}, headers=who.headers)
    assert res.status_code == 201, res.text
    return res.json()


def _error(res: httpx.Response, status: int) -> dict[str, Any]:
    assert res.status_code == status, res.text
    return res.json()["error"]


async def test_machines_are_made_sized_listed_started_stopped_restarted_and_deleted(engine: AsyncEngine) -> None:
    fly = FakeFly()
    pro = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        assert (await client.get("/v1/runtimes", headers=pro.headers)).json() == []
        made = await _made(client, pro, " research ", "medium")
        assert (made["name"], made["size"], made["state"], made["month_seconds"], made["paused"]) == (
            "research",
            "medium",
            "stopped",
            0,
            False,
        )
        assert made["address"] == "https://m_2.glyphh.app" and made["created_at"]
        machine, volume = fly.machines["m_2"], fly.volumes["vol_1"]
        assert machine["config"]["guest"] == {"cpu_kind": "shared", "cpus": 2, "memory_mb": 4096}
        assert volume["size_gb"] == 10 and machine["state"] == "started"
        large = await _made(client, pro, "big", "large")
        assert fly.machines["m_3"]["config"]["guest"] == {"cpu_kind": "performance", "cpus": 2, "memory_mb": 8192}
        doormen = [m["name"] for m in fly.machines.values()].count("doorman")
        assert fly.volumes["vol_2"]["size_gb"] == 20 and doormen == 1
        listed = (await client.get("/v1/runtimes", headers=pro.headers)).json()
        assert [m["name"] for m in listed] == ["research", "big"]
        one = (await client.get(f"/v1/runtimes/{large['id']}", headers=pro.headers)).json()
        assert one == large
        stopped = await client.post(f"/v1/runtimes/{large['id']}/stop", headers=pro.headers)
        assert stopped.json()["state"] == "stopped" and fly.machines["m_3"]["state"] == "stopped"
        assert fly.machines["m_2"]["state"] == "started"  # the other machine untouched
        started = await client.post(f"/v1/runtimes/{large['id']}/start", headers=pro.headers)
        assert started.status_code == 200 and fly.machines["m_3"]["state"] == "started"
        async with engine.begin() as conn:
            await conn.execute(update(Rrotor).where(Rrotor.id == uuid.UUID(large["id"])).values(state="online"))
        before = len(fly.calls)
        assert (await client.post(f"/v1/runtimes/{large['id']}/start", headers=pro.headers)).json()["state"] == "online"
        assert len(fly.calls) == before  # online: not started again
        restarted = await client.post(f"/v1/runtimes/{large['id']}/restart", headers=pro.headers)
        assert restarted.json()["state"] == "stopped" and fly.calls[-1][:2] == ("POST", "/machines/m_3/restart")
        for confirm in ("", "?confirm=Big"):
            res = await client.delete(f"/v1/runtimes/{large['id']}{confirm}", headers=pro.headers)
            assert _error(res, 422)["reason"] == "confirm" and "m_3" in fly.machines
        assert (await client.delete(f"/v1/runtimes/{large['id']}?confirm=big", headers=pro.headers)).status_code == 204
        assert "m_3" not in fly.machines and "vol_2" not in fly.volumes
        assert [m["name"] for m in (await client.get("/v1/runtimes", headers=pro.headers)).json()] == ["research"]
        gone = await client.get(f"/v1/runtimes/{large['id']}", headers=pro.headers)
        assert _error(gone, 404)["code"] == "E_NOT_FOUND"


async def test_a_machine_is_only_its_owners(engine: AsyncEngine) -> None:
    fly = FakeFly()
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        made = await _made(client, ada, "mine")
        base = f"/v1/runtimes/{made['id']}"
        for method, path in (("GET", ""), ("POST", "/start"), ("POST", "/stop"), ("POST", "/restart")):
            assert _error(await client.request(method, base + path, headers=eve.headers), 404)["runtime_id"]
        assert _error(await client.delete(f"{base}?confirm=mine", headers=eve.headers), 404)
        assert (await client.get("/v1/runtimes", headers=eve.headers)).json() == []
        assert _error(await client.get(f"/v1/runtimes/{uuid.uuid4()}", headers=ada.headers), 404)
        assert (await client.get("/v1/runtimes/self", headers=ada.headers)).json() == []  # not taken for an id


async def test_names_sizes_and_the_plans_machines_are_checked(engine: AsyncEngine) -> None:
    fly = FakeFly()
    free, pro = await person(engine), await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        await _made(client, free, "one")
        res = await client.post("/v1/runtimes", json={"name": "two", "size": "small"}, headers=free.headers)
        full = _error(res, 403)
        assert (full["code"], full["reason"], full["limit"], full["used"], full["max"], full["plan"]) == (
            "E_LIMIT",
            "machines",
            "machines",
            1,
            1,
            "Pro",
        )
        await _made(client, pro, "a")
        taken = await client.post("/v1/runtimes", json={"name": "a", "size": "large"}, headers=pro.headers)
        assert (_error(taken, 409)["reason"], _error(taken, 409)["name"]) == ("name", "a")
        await _made(client, pro, "b")
        await _made(client, pro, "c")
        over = await client.post("/v1/runtimes", json={"name": "d", "size": "small"}, headers=pro.headers)
        assert (_error(over, 403)["max"], _error(over, 403)["plan"]) == (3, "Team")
        for body in ({"name": "e", "size": "huge"}, {"name": " ", "size": "small"}, {"name": "e"}):
            assert (await client.post("/v1/runtimes", json=body, headers=pro.headers)).status_code == 422
    async for client in _client(create_app(PROVIDER_SETTINGS, http=fake_http())):
        res = await client.post("/v1/runtimes", json={"name": "x", "size": "small"}, headers=pro.headers)
        assert _error(res, 503)["reason"] == "hosting_off"
    assert set(SIZES) == {"small", "medium", "large"}
    assert SIZES_SAID.startswith("small: shared 1 CPU, 1 GB memory, 3 GB disk; medium: shared 2 CPU, 4 GB memory")


async def test_the_routes_made_for_one_runtime_act_on_the_first_machine(engine: AsyncEngine) -> None:
    fly = FakeFly()
    pro = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        first = (await client.post("/v1/runtime/start", headers=pro.headers)).json()
        listed = (await client.get("/v1/runtimes", headers=pro.headers)).json()
        assert [(m["id"], m["name"], m["size"]) for m in listed] == [(first["runtime_id"], "default", "small")]
        second = await _made(client, pro, "second")
        assert (await client.get("/v1/runtime", headers=pro.headers)).json()["runtime_id"] == first["runtime_id"]
        await client.post(f"/v1/runtimes/{second['id']}/stop", headers=pro.headers)
        again = (await client.post("/v1/runtime/start", headers=pro.headers)).json()
        assert again["runtime_id"] == first["runtime_id"] and fly.machines["m_3"]["state"] == "stopped"
        assert (await client.post("/v1/runtime/stop", headers=pro.headers)).json()["state"] == "stopped"
        assert fly.machines["m_2"]["state"] == "stopped"
        assert (await client.delete("/v1/runtime", headers=pro.headers)).status_code == 204
        assert (await client.get("/v1/runtime", headers=pro.headers)).json()["runtime_id"] == second["id"]
