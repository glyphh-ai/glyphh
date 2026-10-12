"""Needs you: every open question across my machines, and answering one once."""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import tokens
from tests.db.helpers import ask, install, make_machine, make_org, make_thread, make_user


async def _me(engine: AsyncEngine, email: str) -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
    org = await make_org(engine, f"Questions of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        return org, user, {"authorization": f"Bearer {(await tokens.issue(conn, user, org)).access_token}"}


async def test_lists_open_questions_across_my_machines_newest_first(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    org, user, auth = await _me(engine, "list@needs.test")
    mac, laptop = await make_machine(engine, org, user, "studio-mac"), await make_machine(engine, org, user, "laptop")
    scout = await install(engine, mac, org, user, "Scout")
    a = await make_thread(engine, org, user, mac, "Launch note", super_power=scout)
    b = await make_thread(engine, org, user, laptop, "Receipts")
    await ask(engine, org, user, a, "slack.post", scout, minutes_ago=10)
    await ask(engine, org, user, b, "drive.upload", None, minutes_ago=1)
    await ask(engine, org, user, a, "gmail.send", scout, answer="allow")
    other_org, other, _ = await _me(engine, "other@needs.test")
    theirs = await make_machine(engine, other_org, other, "their-mac")
    await ask(engine, other_org, other, await make_thread(engine, other_org, other, theirs, "Theirs"), "x.y")
    page = (await client.get("/v1/needs-you", headers=auth)).json()
    assert page["total"] == 2
    first, second = page["questions"]
    assert (first["tool"], first["machine_name"], first["thread_goal"], first["super_power"]) == (
        "drive.upload",
        "laptop",
        "Receipts",
        None,
    )
    assert (second["tool"], second["machine_name"], second["super_power"]["name"]) == (
        "slack.post",
        "studio-mac",
        "Scout",
    )
    assert second["detail"] == "slack.post something" and second["kind"] == "permission"
    paged = (await client.get("/v1/needs-you", headers=auth, params={"page": 2, "size": 1})).json()
    assert [q["tool"] for q in paged["questions"]] == ["slack.post"]


async def test_answers_once_and_only_mine(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "answer@needs.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    thread = await make_thread(engine, org, user, mac, "Launch note")
    yes, no = await ask(engine, org, user, thread, "slack.post"), await ask(engine, org, user, thread, "drive.delete")
    allowed = (await client.post(f"/v1/needs-you/{yes}/answer", headers=auth, json={"allow": True})).json()
    assert allowed["id"] == str(yes) and allowed["answer"] == "allow" and allowed["answered_at"]
    assert (await client.post(f"/v1/needs-you/{no}/answer", headers=auth, json={"allow": False})).json()[
        "answer"
    ] == "deny"
    again = await client.post(f"/v1/needs-you/{yes}/answer", headers=auth, json={"allow": False})
    assert again.status_code == 409 and again.json()["error"]["reason"] == "answered"
    assert (await client.get("/v1/needs-you", headers=auth)).json()["total"] == 0
    _, _, other_auth = await _me(engine, "nosy@needs.test")
    assert (
        await client.post(f"/v1/needs-you/{uuid.uuid4()}/answer", headers=auth, json={"allow": True})
    ).status_code == 404
    assert (
        await client.post(f"/v1/needs-you/{no}/answer", headers=other_auth, json={"allow": True})
    ).status_code == 404
