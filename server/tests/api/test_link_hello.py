"""The runtime link's door: the token in its header, the hello and its welcome, the runtime online and then offline,
every refusal a close with its reason, the pings, a newer link taking over, and the server closing its links."""

import asyncio
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import tokens
from glyphh_server.ops.license import canonical
from glyphh_server.ops.link import hello as hello_step
from glyphh_server.ops.link import session
from glyphh_server.ops.link.presence import Runtime, bearer
from tests.db.helpers import person
from tests.link import WAIT, closed, connect, hello, linked, local_runtime, receive, runtime_row, self_runtime, server


async def _until_state(engine: AsyncEngine, runtime_id: object, state: str) -> str:
    for _ in range(100):
        row = await runtime_row(engine, runtime_id)
        if row.state == state:
            break
        await asyncio.sleep(0.02)
    return row.state


async def test_a_hello_is_welcomed_and_the_runtime_is_online_until_it_hangs_up(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    async with server() as srv:
        async with connect(srv, rt.token) as ws:
            await ws.send_json(hello(rt, version="1.4.0"))
            welcome = await ws.receive_json(timeout=WAIT)
            assert welcome["type"] == "welcome" and welcome["accepted"] is True
            assert "limits" not in welcome and welcome["licence"] is None and welcome["id"]
            assert welcome["license_key"] is None  # Free: no key, Community
            row = await runtime_row(engine, rt.id)
            assert (row.state, row.image_version) == ("online", "1.4.0") and row.last_seen_at is not None
            seen = row.last_seen_at
        assert await _until_state(engine, rt.id, "offline") == "offline"
    assert (await runtime_row(engine, rt.id)).last_seen_at >= seen


async def test_a_self_hosted_runtime_is_welcomed_with_its_licence_and_keys(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    rt = await self_runtime(engine, ada)
    async with server() as srv, connect(srv, rt.token) as ws:
        await ws.send_json(hello(rt))
        welcome = await ws.receive_json(timeout=WAIT)
        assert "limits" not in welcome
        key = (await srv.http.get("/v1/license/key", headers=ada.headers)).json()
    assert welcome["keys"] == []
    payload = welcome["licence"]["payload"]
    assert (payload["install_id"], payload["user_id"], payload["plan"]) == (None, str(ada.user_id), "Pro")
    assert (payload["kind"], payload["runtime_id"], payload["grace_days"]) == ("link", str(rt.id), 14)
    assert payload["mods"] == {"ada": {"limits": {"precedents": None}}} and payload["limits"] == {"machines": 3}
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"]))
    public.verify(base64.b64decode(welcome["licence"]["signature"]), canonical(payload))
    ctx = session.Context(engine, None, None)  # type: ignore[arg-type]
    runtime = Runtime(rt.id, ada.user_id, ada.org_id, "self", "https://rrotor.acme.test")
    assert (await session._welcome(ctx, runtime)).licence is None  # no key to sign with: no licence


async def test_a_link_without_a_good_token_is_refused_with_its_reason(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    async with engine.begin() as conn:
        await tokens.revoke_install(conn, ada.install_id)
    async with server() as srv:
        for token, reason in (
            (None, "Send the runtime's token"),
            ("not-a-token", "not valid"),
            (rt.token, "install was signed out"),
        ):
            async with connect(srv, token) as ws:
                code, said = await closed(ws)
            assert code == 4401 and reason in said
    assert (await runtime_row(engine, rt.id)).state == "stopped"
    assert bearer("Basic abc") is None and bearer("bearer  tok ") == "tok" and bearer("Bearer ") is None


@pytest.mark.parametrize(
    ("said", "code", "reason"),
    [
        ("not json", 4400, "must be hello"),
        ({"type": "hello", "protocol": 3}, 4400, "must be hello"),
        ({"type": "hello", "protocol": 2}, 4400, "must be hello"),
        ({"type": "result", "protocol": 3}, 4400, "must be hello"),
        ({"type": "hello", "protocol": 1}, 4426, "protocol 3"),
        ({"type": "hello", "protocol": 4}, 4426, "protocol 3"),
        ({"type": "hello"}, 4426, "protocol 3"),
        ("protocol 1", 4426, "Update the rrotor"),
        ("other runtime", 4400, "another runtime"),
        ("other mode", 4400, "another runtime"),
        ("hosted", 4400, "must be hello"),
    ],
)
async def test_the_first_message_must_be_a_hello_of_protocol_3_or_2_for_this_runtime(
    engine: AsyncEngine, said: object, code: int, reason: str
) -> None:
    ada, eve = await person(engine), await person(engine)
    rt, other = await local_runtime(engine, ada), await local_runtime(engine, eve)
    special = {
        "protocol 1": hello(rt, protocol=1),
        "other runtime": hello(rt, runtime_id=str(other.id)),
        "other mode": hello(rt, mode="self"),
        "hosted": hello(rt, mode="hosted"),
    }
    message = special.get(said, said) if isinstance(said, str) else said
    async with server() as srv, connect(srv, rt.token) as ws:
        await ws.send_text(message if isinstance(message, str) else json.dumps(message))
        got, why = await closed(ws)
    assert got == code and reason in why
    assert (await runtime_row(engine, rt.id)).state == "stopped"


async def test_a_rrotor_that_says_nothing_is_closed_and_one_that_hangs_up_is_let_go(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hello_step, "HELLO_WAIT", 0.1)
    rt = await local_runtime(engine, await person(engine))
    async with server() as srv:
        async with connect(srv, rt.token) as ws:
            assert await closed(ws) == (4400, "Say hello within 0.1 seconds.")
        async with connect(srv, rt.token):
            pass
        await asyncio.sleep(0.05)
    assert (await runtime_row(engine, rt.id)).state == "stopped"


async def test_pings_both_ways_and_silence_closes_the_link(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session, "PING_EVERY", 0.05)
    rt = await local_runtime(engine, await person(engine))
    async with server() as srv, linked(srv, rt) as ws:
        await ws.send_json({"type": "ping", "id": "p1"})
        assert (await receive(ws, "pong"))["type"] == "pong"
        for _ in range(4):  # answered, so the link stays past three pings
            ping = await ws.receive_json(timeout=WAIT)
            assert ping["type"] == "ping"
            await ws.send_json({"type": "pong", "id": f"re-{ping['id']}"})
        assert await closed(ws) == (4408, "Nothing heard for 0.15 seconds.")
    assert await _until_state(engine, rt.id, "offline") == "offline"


async def test_unreadable_messages_are_skipped_and_the_link_stays(engine: AsyncEngine) -> None:
    rt = await local_runtime(engine, await person(engine))
    async with server() as srv, linked(srv, rt) as ws:
        await ws.send_text("{not json")
        await ws.send_bytes(b"\x00\x01")
        for message in (
            {"type": "nope", "id": "x"},
            {"type": "usage", "id": "u"},
            {"type": "usage", "id": "u", "seq": 0},
            {"type": "result", "id": ""},
            {"type": "ack", "id": "a", "of": "w"},
        ):
            await ws.send_json(message)
        await ws.send_json({"type": "ping", "id": "still-here"})
        assert (await ws.receive_json(timeout=WAIT))["type"] == "pong"
        assert (await runtime_row(engine, rt.id)).seq == 0


async def test_a_newer_link_takes_over_here_or_on_another_process(engine: AsyncEngine) -> None:
    rt = await local_runtime(engine, await person(engine))
    async with server() as a, server() as b:
        async with linked(a, rt) as first, linked(a, rt) as second:
            assert await closed(first) == (4409, "A newer link of this runtime took over.")
            await asyncio.sleep(0.05)
            assert (await runtime_row(engine, rt.id)).state == "online"
            async with linked(b, rt) as third:
                assert (await closed(second))[0] == 4409
                await asyncio.sleep(0.05)
                assert (await runtime_row(engine, rt.id)).state == "online"
                await third.send_json({"type": "ping", "id": "p"})
                assert (await receive(third, "pong"))["type"] == "pong"
        assert await _until_state(engine, rt.id, "offline") == "offline"


async def test_a_stopping_server_closes_its_links_so_they_reconnect(engine: AsyncEngine) -> None:
    rt = await local_runtime(engine, await person(engine))
    async with server() as srv, linked(srv, rt) as ws:
        await srv.app.state.hub.close_all()
        assert await closed(ws) == (1012, "The server is restarting. Reconnect.")
