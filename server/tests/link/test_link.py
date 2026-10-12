"""The machine link: a machine signs in with its token, says hello, and its reports change thread records."""

import json
import uuid

import pytest
from httpx_ws import WebSocketDisconnect, aconnect_ws
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Machine, NeedsYou, Thread
from tests.db.helpers import install, make_thread
from tests.link.conftest import event, live, machine, member, until

URL = "http://test/v1/machine/link"
HELLO = json.dumps({"type": "hello", "protocol": 1, "version": "1.4.2"})


async def _machine_row(engine: AsyncEngine, machine_id: uuid.UUID):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Machine.online, Machine.version).where(Machine.id == machine_id))).one()


async def _thread(engine: AsyncEngine, thread: uuid.UUID):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Thread.status, Thread.last_seq).where(Thread.id == thread))).one()


async def test_a_machine_without_its_token_is_refused(engine: AsyncEngine) -> None:
    async with live() as app:
        for headers in ({}, {"authorization": "Bearer not-a-machine"}, {"authorization": "Basic x"}):
            with pytest.raises(WebSocketDisconnect) as refused:
                async with aconnect_ws(URL, app, headers=headers) as ws:
                    await ws.receive_text()
            assert refused.value.code == 4401


async def test_hello_brings_it_online_with_its_version_and_going_takes_it_off(engine: AsyncEngine) -> None:
    async with live() as app:
        who = await member(engine, "hello@link.test")
        mac, token = await machine(engine, who)
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            await ws.send_text(HELLO)
            assert await until(lambda: _online(engine, mac, True)) == ("1.4.2",)
            assert app.app.state.hub.online(mac)  # type: ignore[attr-defined]
        assert await until(lambda: _online(engine, mac, False))
        assert not app.app.state.hub.online(mac)  # type: ignore[attr-defined]


async def _online(engine: AsyncEngine, mac: uuid.UUID, online: bool):  # type: ignore[no-untyped-def]
    row = await _machine_row(engine, mac)
    return (row.version,) if row.online == online else None


async def test_a_machine_on_another_protocol_is_told_to_upgrade(engine: AsyncEngine) -> None:
    async with live() as app:
        who = await member(engine, "upgrade@link.test")
        _, token = await machine(engine, who)
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            await ws.send_text(json.dumps({"type": "hello", "protocol": 2, "version": "9.0.0"}))
            with pytest.raises(WebSocketDisconnect) as closed:
                await ws.receive_text()
        assert closed.value.code == 4426


async def test_events_change_the_thread_record_and_open_questions(engine: AsyncEngine) -> None:
    async with live() as app:
        who = await member(engine, "events@link.test")
        mac, token = await machine(engine, who)
        scout = await install(engine, mac, who.org, who.user, "Scout")
        thread = await make_thread(engine, who.org, who.user, mac, "Launch note", super_power=scout)
        other = await member(engine, "other@link.test")
        theirs, _ = await machine(engine, other, "their-mac")
        not_mine = await make_thread(engine, other.org, other.user, theirs, "Theirs")
        async with aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
            await ws.send_text("{not json")
            await ws.send_text(json.dumps({"type": "session.dance"}))
            await ws.send_text(event(not_mine, 9, {"kind": "status", "status": "stuck"}))
            await ws.send_text(event(thread, 1, {"kind": "status", "status": "thinking"}))
            await ws.send_text(
                event(
                    thread,
                    2,
                    {
                        "kind": "needs_you",
                        "id": "req-1",
                        "ask": "permission",
                        "tool": "slack.post",
                        "detail": "x" * 300,
                    },
                    scout,
                )
            )
            await ws.send_text(event(thread, 3, {"kind": "status", "status": "needs_you"}, scout))
            assert await until(lambda: _is(engine, thread, ("needs_you", 3)))
            await ws.send_text(event(thread, 2, {"kind": "needs_you", "id": "req-1", "tool": "slack.post"}, scout))
            await ws.send_text(json.dumps({"type": "session.refused", "session": "s", "reason": "It could not start"}))
            await ws.send_text(event(thread, 4, {"kind": "text", "text": "ok"}))
            assert await until(lambda: _is(engine, thread, ("needs_you", 4)))
        assert (await _thread(engine, not_mine)).status == "idle"
        async with engine.connect() as conn:
            asked = (await conn.execute(select(NeedsYou).where(NeedsYou.thread_id == thread))).all()
        assert len(asked) == 1 and (asked[0].session, asked[0].ask_id, asked[0].super_power_id) == (
            str(thread),
            "req-1",
            scout,
        )
        assert len(asked[0].detail) == 200 and asked[0].answer is None
    stuck = await make_thread(engine, who.org, who.user, mac, "Never started")
    async with live() as app, aconnect_ws(URL, app, headers={"authorization": f"Bearer {token}"}) as ws:
        refusal = {"type": "session.refused", "session": str(stuck), "thread": str(stuck), "reason": "No space left"}
        await ws.send_text(json.dumps(refusal))
        await ws.send_text(json.dumps({**refusal, "thread": str(not_mine)}))
        assert await until(lambda: _is(engine, stuck, ("stuck", 0)))
    assert (await _thread(engine, not_mine)).status == "idle"


async def _is(engine: AsyncEngine, thread: uuid.UUID, want: tuple[str, int]) -> bool:
    row = await _thread(engine, thread)
    return (row.status, row.last_seq) == want
