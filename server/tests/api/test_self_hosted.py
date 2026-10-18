"""Self-hosted runtimes: registered by name and public address (the token shown once, the environment filled in),
listed, their token rotated (the old one refused, its link closed, here or on another process), deleted; linked,
welcomed with a licence that carries its grace and unlimited precedents; keys made for one; never tallied."""

import base64
import json
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unavailable
from glyphh_server.models import Rrotor
from glyphh_server.ops import tend
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import Keys
from tests.db.helpers import Person, person
from tests.link import Rt, closed, connect, hello, linked, receive, runtime_row, server

HOST = "rrotor.acme.test"


async def made(client: httpx.AsyncClient, who: Person, url: str = f"https://{HOST}", name: str = "Acme") -> Any:
    res = await client.post("/v1/runtimes/self", json={"name": name, "public_url": url}, headers=who.headers)
    assert res.status_code == 201, res.text
    return res.json()


def rt(body: dict[str, Any]) -> Rt:
    return Rt(uuid.UUID(body["id"]), body["token"], "self")


def verifies(key: dict[str, str], lic: dict[str, Any]) -> None:
    """As rrotor checks it: the public key, over the payload's canonical JSON as received."""
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"]))
    canonical = json.dumps(lic["payload"], sort_keys=True, separators=(",", ":")).encode()
    public.verify(base64.b64decode(lic["signature"]), canonical)


async def test_a_self_hosted_runtime_is_registered_with_its_environment_and_listed(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine)
    body = await made(client, ada, "https://RRotor.Acme.test/", " Acme prod ")
    assert (body["name"], body["public_url"]) == ("Acme prod", f"https://{HOST}")
    assert body["env"] == {
        "RROTOR_MODE": "self",
        "RROTOR_SERVER": "http://localhost:8080",
        "RROTOR_RUNTIME_ID": body["id"],
        "RROTOR_RUNTIME_TOKEN": body["token"],
        "RROTOR_PUBLIC_HOST": HOST,
    }
    row = await runtime_row(engine, uuid.UUID(body["id"]))
    assert (row.mode, row.state, row.install_id, row.fly_machine_id) == ("self", "stopped", None, None)
    assert row.token_hash != body["token"]
    again = await client.post(
        "/v1/runtimes/self", json={"name": "x", "public_url": f"https://{HOST}"}, headers=ada.headers
    )
    assert again.status_code == 409 and again.json()["error"]["reason"] == "registered"
    await made(client, ada, "https://b.acme.test", "Backup")
    await made(client, eve, f"https://{HOST}", "Eve's")  # another person may name the same host: their own
    listed = (await client.get("/v1/runtimes/self", headers=ada.headers)).json()
    assert [r["name"] for r in listed] == ["Acme prod", "Backup"]
    assert listed[0] == {
        "id": body["id"],
        "name": "Acme prod",
        "public_url": f"https://{HOST}",
        "state": "stopped",
        "version": None,
        "last_seen_at": None,
        "last_heartbeat_at": None,
    }
    assert (await client.get("/v1/runtimes/self")).status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        f"http://{HOST}",
        f"https://{HOST}/mcp",
        f"https://{HOST}:8443",
        f"https://{HOST}?x=1",
        f"https://{HOST}#top",
        f"https://me@{HOST}",
        "https://under_score.test",
        "https://-bad.test",
        "https://[::1]",
        HOST,
        "https://",
    ],
)
async def test_an_address_that_is_not_just_an_https_host_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine, url: str
) -> None:
    ada = await person(engine)
    res = await client.post("/v1/runtimes/self", json={"name": "A", "public_url": url}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "public_url", url


async def test_glyphhs_own_addresses_and_a_blank_name_are_refused(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    for url in ("https://glyphh.app", "https://m1a2b3c4d5.glyphh.app", "https://localhost"):
        res = await client.post("/v1/runtimes/self", json={"name": "A", "public_url": url}, headers=ada.headers)
        assert res.status_code == 422 and "Glyphh's own" in res.json()["error"]["message"], url
    res = await client.post(
        "/v1/runtimes/self", json={"name": "  ", "public_url": f"https://{HOST}"}, headers=ada.headers
    )
    assert res.status_code == 422


async def test_it_links_and_its_welcome_carries_a_licence_with_grace_and_unlimited_precedents(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    runtime = rt(await made(client, ada))
    async with server() as srv, connect(srv, runtime.token) as ws:
        await ws.send_json(hello(runtime, version="2.0.0"))
        welcome = await ws.receive_json(timeout=5)
        assert (welcome["accepted"], welcome["keys"], "limits" in welcome) == (True, [], False)
        verifies((await srv.http.get("/v1/license/key", headers=ada.headers)).json(), welcome["licence"])
        p = welcome["licence"]["payload"]
        assert (p["runtime_id"], p["kind"], p["grace_days"], p["install_id"]) == (str(runtime.id), "link", 14, None)
        assert uuid.UUID(p["licence_id"]) and p["plan"] == "Pro"
        assert p["mods"] == {"ada": {"limits": {"precedents": None}}} and p["features"]["sync"] is True
        listed = (await client.get("/v1/runtimes/self", headers=ada.headers)).json()[0]
        assert (listed["state"], listed["version"]) == ("online", "2.0.0") and listed["last_seen_at"]


async def test_rotating_the_token_refuses_the_old_one_and_closes_its_link_here_or_elsewhere(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine), await person(engine)
    runtime = rt(await made(client, ada))
    async with server() as one, server() as two:
        async with linked(one, runtime) as ws:  # held by one; rotated through two: dropped over Redis
            res = await two.http.post(f"/v1/runtimes/self/{runtime.id}/token", headers=ada.headers)
            assert res.status_code == 200, res.text
            code, reason = await closed(ws)
            assert (code, reason) == (4401, "This runtime's token was replaced. Use the new one.")
        async with connect(one, runtime.token) as ws:
            assert (await closed(ws))[0] == 4401
        fresh = Rt(runtime.id, res.json()["token"], "self")
        async with linked(one, fresh) as ws:  # held by one; rotated through one: closed at once
            res = await one.http.post(f"/v1/runtimes/self/{runtime.id}/token", headers=ada.headers)
            assert res.status_code == 200 and (await closed(ws))[0] == 4401
        assert (await runtime_row(engine, runtime.id)).seq == 0
    res = await client.post(f"/v1/runtimes/self/{runtime.id}/token", headers=eve.headers)
    assert res.status_code == 404 and res.json()["error"]["code"] == "E_NOT_FOUND"


async def test_deleting_it_drops_its_link_and_its_record(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    runtime = rt(await made(client, ada))
    assert (await client.delete(f"/v1/runtimes/self/{runtime.id}", headers=eve.headers)).status_code == 404
    async with server() as srv, linked(srv, runtime) as ws:
        res = await srv.http.delete(f"/v1/runtimes/self/{runtime.id}", headers=ada.headers)
        assert res.status_code == 204
        assert await closed(ws) == (4401, "This runtime was deleted from Glyphh.")
    async with engine.connect() as conn:
        assert (await conn.execute(select(Rrotor.id).where(Rrotor.id == runtime.id))).first() is None
    assert (await client.get("/v1/runtimes/self", headers=ada.headers)).json() == []
    assert (await client.delete(f"/v1/runtimes/self/{runtime.id}", headers=ada.headers)).status_code == 404


async def test_a_key_is_made_for_a_self_hosted_runtime_and_reaches_it(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine), await person(engine)
    runtime = rt(await made(client, ada))
    theirs = rt(await made(client, eve, "https://eve.acme.test"))
    async with server() as srv, linked(srv, runtime) as ws:
        res = await srv.http.post(
            "/v1/runtime/keys", json={"name": "CRM", "runtime_id": str(runtime.id)}, headers=ada.headers
        )
        assert res.status_code == 201, res.text
        assert res.json()["runtime_id"] == str(runtime.id)
        assert len((await receive(ws, "keys"))["hashes"]) == 1
    res = await client.post("/v1/runtime/keys", json={"name": "x", "runtime_id": str(theirs.id)}, headers=ada.headers)
    assert res.status_code == 404
    listed = (await client.get("/v1/runtime/keys", headers=ada.headers)).json()
    assert [k["runtime_id"] for k in listed] == [str(runtime.id)]


async def test_the_tally_never_counts_it_and_a_call_to_it_offline_says_so(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine)
    runtime = rt(await made(client, ada))
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime.id).values(state="online", month_seconds=10**7))
    await tend.tally(engine, 60)
    row = await runtime_row(engine, runtime.id)
    assert (row.month, row.month_seconds) == (None, 10**7)
    away = SimpleNamespace(id=runtime.id, mode="self", last_seen_at=None)
    with pytest.raises(Unavailable) as refused:
        await calls.deliver(Hub(redis), away, Keys(hashes=[]))  # type: ignore[arg-type]
    assert refused.value.message.startswith("Your self-hosted runtime is not connected.")
