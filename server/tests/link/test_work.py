"""Working a thread through its machine: start, say, stop, answer, delete; and watching it live."""

import asyncio
import json
import uuid

import httpx
from httpx_ws import aconnect_ws
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api import thread_work
from glyphh_server.models import ThreadCrew
from glyphh_server.ops.threads.run import goal_of
from tests.db.helpers import install, make_thread
from tests.link.conftest import event, live, machine, member, until

URL = "http://test/v1/machine/link"
HELLO = json.dumps({"type": "hello", "protocol": 1, "version": "1.4.2"})


async def test_starting_saying_stopping_and_answering_reach_the_machine(engine: AsyncEngine) -> None:
    async with live() as app:
        who = await member(engine, "work@link.test")
        mac, token = await machine(engine, who)
        clips = await install(engine, mac, who.org, who.user, "Clip Studio")
        inbox = await install(engine, mac, who.org, who.user, "Inbox Zero")
        url = f"/v1/machines/{mac}/threads"
        offline = await app.post(url, headers=who.auth, json={"prompt": "Reels"})
        assert offline.status_code == 409 and offline.json()["error"]["reason"] == "offline"
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            await ws.send_text(HELLO)
            await until(lambda: _online(app, mac))
            made = await app.post(
                url,
                headers=who.auth,
                json={
                    "prompt": "Turn this video into reels\nmore",
                    "super_power": str(clips),
                    "model": "sonnet",
                    "mode": "autonomous",
                    "engine": "codex",
                },
            )
            assert (
                made.status_code == 201
                and made.json()["goal"] == "Turn this video into reels"
                and made.json()["status"] == "working"
            )
            thread = made.json()["id"]
            assert json.loads(await ws.receive_text()) == {
                "type": "session.start",
                "session": thread,
                "thread": thread,
                "engine": "codex",
                "prompt": "Turn this video into reels\nmore",
                "mode": "autonomous",
                "super_power": str(clips),
                "model": "sonnet",
            }
            crew = await app.post(
                url, headers=who.auth, json={"prompt": "Acme call prep", "crew": [str(inbox), str(inbox)]}
            )
            assert json.loads(await ws.receive_text())["type"] == "session.start" and crew.json()["super_power"] is None
            async with engine.connect() as conn:
                assert (
                    await conn.execute(
                        select(ThreadCrew.super_power_id).where(ThreadCrew.thread_id == uuid.UUID(crew.json()["id"]))
                    )
                ).all() == [(inbox,)]
            assert (
                await app.post(f"/v1/threads/{thread}/say", headers=who.auth, json={"text": "Shorter"})
            ).status_code == 204
            assert json.loads(await ws.receive_text()) == {"type": "session.send", "session": thread, "text": "Shorter"}
            assert (await app.post(f"/v1/threads/{thread}/stop", headers=who.auth)).status_code == 204
            assert json.loads(await ws.receive_text()) == {"type": "session.stop", "session": thread}
            await ws.send_text(
                event(
                    uuid.UUID(thread),
                    1,
                    {"kind": "needs_you", "id": "req-9", "tool": "drive.delete", "detail": "x"},
                    clips,
                )
            )
            question = await until(lambda: _question(app, who.auth))
            assert (
                await app.post(f"/v1/needs-you/{question}/answer", headers=who.auth, json={"allow": True})
            ).status_code == 200
            assert json.loads(await ws.receive_text()) == {
                "type": "session.answer",
                "session": thread,
                "id": "req-9",
                "allow": True,
            }
        await until(lambda: _offline(app, mac))
        assert (await app.post(f"/v1/threads/{thread}/say", headers=who.auth, json={"text": "x"})).status_code == 409


async def _online(live: httpx.AsyncClient, mac: uuid.UUID) -> bool:
    return bool(live.app.state.hub.online(mac))  # type: ignore[attr-defined]


async def _offline(live: httpx.AsyncClient, mac: uuid.UUID) -> bool:
    return not await _online(live, mac)


async def _question(live: httpx.AsyncClient, auth: dict[str, str]) -> str | None:
    found = (await live.get("/v1/needs-you", headers=auth)).json()["questions"]
    return found[0]["id"] if found else None


async def test_only_my_super_powers_crew_a_thread(engine: AsyncEngine) -> None:
    async with live() as app:
        who = await member(engine, "crew@link.test")
        mac, token = await machine(engine, who)
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            await ws.send_text(HELLO)
            await until(lambda: _online(app, mac))
            refused = await app.post(
                f"/v1/machines/{mac}/threads", headers=who.auth, json={"prompt": "x", "crew": [str(uuid.uuid4())]}
            )
            assert refused.status_code == 404


async def test_watching_streams_each_event_until_the_thread_is_deleted(engine: AsyncEngine, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async with live() as app:
        monkeypatch.setattr(thread_work, "PING_SECONDS", 0.05)
        who = await member(engine, "watch@link.test")
        mac, token = await machine(engine, who)
        thread = await make_thread(engine, who.org, who.user, mac, "Watched")
        assert (await app.get(f"/v1/threads/{thread}/events")).status_code == 401
        assert (await app.get(f"/v1/threads/{uuid.uuid4()}/events", headers=who.auth)).status_code == 404
        hub = app.app.state.hub  # type: ignore[attr-defined]
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            watching = asyncio.create_task(app.get(f"/v1/threads/{thread}/events", headers=who.auth))
            await until(lambda: _watched(hub, thread))
            await asyncio.sleep(0.12)
            await ws.send_text(event(thread, 1, {"kind": "text", "text": "Sorted."}))
            await ws.send_text(
                json.dumps({"type": "session.refused", "session": "s", "thread": str(thread), "reason": "Busy"})
            )
            await asyncio.sleep(0.1)
            await app.patch(f"/v1/threads/{thread}", headers=who.auth, json={"archived": True})
            assert (await app.delete(f"/v1/threads/{thread}", headers=who.auth)).status_code == 204
            assert json.loads(await ws.receive_text()) == {"type": "thread.delete", "thread": str(thread)}
            body = (await watching).text
        assert body.startswith(": watching\n\n") and ": ping\n\n" in body
        assert f'id: 1\nevent: session.event\ndata: {{"type": "session.event", "session": "{thread}"' in body
        assert "event: session.refused" in body


async def _watched(hub, thread: uuid.UUID) -> bool:  # type: ignore[no-untyped-def]
    return bool(hub._watchers.get(thread))


def test_a_threads_goal_is_the_first_line_cut_short() -> None:
    assert goal_of("  Reels\nmore") == "Reels"
    assert goal_of("x" * 300) == "x" * 199 + "…"
