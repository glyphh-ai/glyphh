"""Threads: a machine's Recents, one thread, changing and deleting one. Only the record: messages are on the machine."""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import tokens
from tests.db.helpers import ask, install, make_machine, make_org, make_thread, make_user


async def _me(engine: AsyncEngine, email: str) -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
    org = await make_org(engine, f"Threads of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        return org, user, {"authorization": f"Bearer {(await tokens.issue(conn, user, org)).access_token}"}


async def test_recents_lists_pinned_first_then_the_newest_with_crews(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    org, user, auth = await _me(engine, "recents@threads.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    clips = await install(engine, mac, org, user, "Clip Studio")
    inbox = await install(engine, mac, org, user, "Inbox Zero")
    deal = await install(engine, mac, org, user, "Deal Desk")
    await make_thread(engine, org, user, mac, "Standup notes", minutes_ago=30)
    acme = await make_thread(engine, org, user, mac, "Acme call prep", crew=(inbox, deal), minutes_ago=5)
    yt = await make_thread(
        engine, org, user, mac, "YouTube to Instagram", super_power=clips, minutes_ago=60, pinned=True
    )
    await make_thread(engine, org, user, mac, "Old receipts", archived=True)
    await ask(engine, org, user, acme, "slack.post", inbox)
    page = (await client.get(f"/v1/machines/{mac}/threads", headers=auth)).json()
    assert page["machine"] == "studio-mac" and page["total"] == 3
    assert [t["goal"] for t in page["threads"]] == ["YouTube to Instagram", "Acme call prep", "Standup notes"]
    first, second = page["threads"][0], page["threads"][1]
    assert first["id"] == str(yt) and first["super_power"]["name"] == "Clip Studio" and first["crew"] == []
    assert [c["name"] for c in second["crew"]] == ["Inbox Zero", "Deal Desk"] and second["super_power"] is None
    assert second["needs_you"] == 1 and page["threads"][2]["needs_you"] == 0
    assert {c["super_power"]["name"]: c["threads"] for c in page["crew"]} == {
        "Clip Studio": 1,
        "Deal Desk": 1,
        "Inbox Zero": 1,
    }
    archived = (await client.get(f"/v1/machines/{mac}/threads", headers=auth, params={"archived": "true"})).json()
    assert [t["goal"] for t in archived["threads"]] == ["Old receipts"]


async def test_recents_searches_by_goal_and_narrows_to_a_super_power(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    org, user, auth = await _me(engine, "search@threads.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    clips = await install(engine, mac, org, user, "Clip Studio")
    scout = await install(engine, mac, org, user, "Scout")
    await make_thread(engine, org, user, mac, "Reels from the demo day talk", super_power=clips)
    await make_thread(engine, org, user, mac, "Podcast clips 100%_ done", crew=(clips, scout), minutes_ago=1)
    await make_thread(engine, org, user, mac, "Launch note", super_power=scout, minutes_ago=2)
    url = f"/v1/machines/{mac}/threads"
    assert (await client.get(url, headers=auth, params={"q": " clips "})).json()["total"] == 1
    assert (await client.get(url, headers=auth, params={"q": "%_"})).json()["total"] == 1
    by_clips = (await client.get(url, headers=auth, params={"super_power": str(clips)})).json()
    assert [t["goal"] for t in by_clips["threads"]] == ["Reels from the demo day talk", "Podcast clips 100%_ done"]
    paged = (await client.get(url, headers=auth, params={"page": 2, "size": 2})).json()
    assert [t["goal"] for t in paged["threads"]] == ["Launch note"] and paged["total"] == 3


async def test_only_my_machines_threads(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, _, auth = await _me(engine, "mine@threads.test")
    other_org, other, other_auth = await _me(engine, "theirs@threads.test")
    theirs = await make_machine(engine, other_org, other, "their-mac")
    thread = await make_thread(engine, other_org, other, theirs, "Their thread")
    assert (await client.get(f"/v1/machines/{theirs}/threads", headers=auth)).status_code == 404
    assert (await client.get(f"/v1/threads/{thread}", headers=auth)).json()["error"]["code"] == "E_NOT_FOUND"
    assert (await client.patch(f"/v1/threads/{thread}", headers=auth, json={"pinned": True})).status_code == 404
    assert (await client.get(f"/v1/threads/{thread}", headers=other_auth)).status_code == 200


async def test_one_thread_with_its_machine_and_open_questions(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "one@threads.test")
    mac = await make_machine(engine, org, user, "studio-mac", online=False)
    scout = await install(engine, mac, org, user, "Scout")
    thread = await make_thread(engine, org, user, mac, "Launch note", super_power=scout)
    await ask(engine, org, user, thread, "slack.post", scout, minutes_ago=1)
    await ask(engine, org, user, thread, "gmail.send", None)
    await ask(engine, org, user, thread, "drive.delete", scout, answer="deny")
    one = (await client.get(f"/v1/threads/{thread}", headers=auth)).json()
    assert one["thread"]["goal"] == "Launch note" and one["thread"]["needs_you"] == 2
    assert one["machine"] == {"id": str(mac), "name": "studio-mac", "online": False, "last_seen_at": None}
    assert [q["tool"] for q in one["questions"]] == ["gmail.send", "slack.post"]
    assert one["questions"][0]["super_power"] is None and one["questions"][1]["super_power"]["name"] == "Scout"


async def test_rename_pin_archive_and_delete_for_good(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "edit@threads.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    thread = await make_thread(engine, org, user, mac, "Draft")
    url = f"/v1/threads/{thread}"
    renamed = (await client.patch(url, headers=auth, json={"goal": "  Acme call prep  ", "pinned": True})).json()
    assert renamed["goal"] == "Acme call prep" and renamed["pinned_at"] is not None
    assert (await client.patch(url, headers=auth, json={})).json()["goal"] == "Acme call prep"
    assert (await client.patch(url, headers=auth, json={"pinned": False})).json()["pinned_at"] is None
    assert (await client.patch(url, headers=auth, json={"goal": "x" * 501})).status_code == 422
    refused = await client.delete(url, headers=auth)
    assert refused.status_code == 409 and refused.json()["error"]["reason"] == "not_archived"
    assert (await client.patch(url, headers=auth, json={"archived": True})).json()["archived_at"] is not None
    assert (await client.patch(url, headers=auth, json={"archived": False})).json()["archived_at"] is None
    await client.patch(url, headers=auth, json={"archived": True})
    assert (await client.delete(url, headers=auth)).status_code == 204
    assert (await client.get(url, headers=auth)).status_code == 404
