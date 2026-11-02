"""Org apps (docs/specs/apps.md): the catalogue filled from a rrotor's `deployed` up the link (its type from the
manifest), listed by roles and type, searched and paged, reviewed by the admin or a reviewer group's member (each
review told down the link, in the names of the rrotor's protocol), the welcome carrying the runtime's rows and the
org's reviewers, and the connector's tools."""

import uuid
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OrgSso, User
from glyphh_server.ops import apps as ops
from glyphh_server.ops import catalogue
from tests.connector import granted, rpc, tool
from tests.db.helpers import Person, member, person
from tests.link import WAIT, Rt, connect, hello, holding, linked, local_runtime, receive, self_runtime, server

SHA: str = "0123456789abcdef0123456789abcdef01234567"
HOST: str = "https://rrotor.acme.test"


def manifest(
    title: str = "Deploy failures", roles: list[str] | None = None, kind: str = "app", type: str | None = None
) -> dict[str, Any]:
    app: dict[str, Any] = {"entry": "index.html", "title": title, "roles": roles or []}
    if type is not None:
        app["type"] = type
    return {
        "name": "deploy-failures",
        "kind": kind,
        "description": "Last week's deploy failures by service.",
        "app": app,
    }


def deployed(program: str, version: int = 1, by: str | None = None, **over: Any) -> dict[str, Any]:
    said = {"type": "deployed", "id": f"d-{program}-{version}", "program": program, "version": version}
    return {**said, "commit_sha": SHA, "repo": None, "manifest": manifest(), "by": by, **over}


async def publish(rt: Rt, message: dict[str, Any]) -> None:
    """A rrotor on the link says it deployed something: acked once the catalogue has it."""
    async with server() as srv, linked(srv, rt) as ws:
        await ws.send_json(message)
        assert (await receive(ws, "ack"))["of"] == message["id"]


async def with_groups(engine: AsyncEngine, who: Person, groups: list[str]) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == who.user_id).values(groups=groups))


async def with_reviewers(engine: AsyncEngine, org_id: uuid.UUID, reviewers: list[str]) -> None:
    async with engine.begin() as conn:
        values = {"org_id": org_id, "issuer": "https://idp.test", "client_id": "c", "client_secret": "v1.x"}
        await conn.execute(
            upsert(OrgSso)
            .values(**values, reviewers=reviewers)
            .on_conflict_do_update(index_elements=["org_id"], set_={"reviewers": reviewers})
        )


async def listed(client: httpx.AsyncClient, who: Person, **params: Any) -> dict[str, Any]:
    res = await client.get("/v1/apps", params=params, headers=who.headers)
    assert res.status_code == 200, res.text
    return res.json()


async def test_a_deployed_app_is_catalogued_as_a_draft_and_listed_to_reviewers_only(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    bob = await member(engine, ada.org_id)
    rt = await self_runtime(engine, ada, HOST)
    await publish(rt, deployed("deploy-failures", by=str(bob.user_id), manifest=manifest(type="dashboard")))
    await publish(rt, deployed("daily_sales", manifest={"name": "daily_sales", "kind": "program"}))  # not an app
    drafts = await listed(client, ada, state="draft")
    assert (drafts["total"], drafts["page"], drafts["per_page"]) == (1, 1, 24)
    (one,) = drafts["apps"]
    assert (one["name"], one["title"], one["description"], one["type"], one["version"], one["commit_sha"]) == (
        "deploy-failures",
        "Deploy failures",
        "Last week's deploy failures by service.",
        "dashboard",
        1,
        SHA,
    )
    assert (one["state"], one["roles"], one["runtime_id"], one["runtime_name"], one["runtime_url"]) == (
        "draft",
        [],
        str(rt.id),
        "Acme",
        HOST,
    )
    assert one["url"] == f"{HOST}/apps/deploy-failures/" and one["reviewed_by"] is None and one["reason"] is None
    assert one["submitted_by"] == {"id": str(bob.user_id), "name": "Grace Hopper", "email": bob.email}
    assert (await listed(client, ada))["apps"] == []  # nothing approved yet
    refused = await client.get("/v1/apps", params={"state": "draft"}, headers=bob.headers)
    assert (refused.status_code, refused.json()["error"]["reason"]) == (403, "reviewer")
    assert (await client.get(f"/v1/apps/{one['id']}", headers=bob.headers)).status_code == 404  # not yet
    assert (await client.get(f"/v1/apps/{one['id']}", headers=ada.headers)).json()["id"] == one["id"]
    assert (await client.get(f"/v1/apps/{uuid.uuid4()}", headers=ada.headers)).status_code == 404
    assert (await client.get("/v1/artifacts", headers=ada.headers)).status_code == 404  # the first cut's name is gone
    again = manifest("Deploy failures v2", ["sre"], type="poster")  # a type outside the six is a page
    await publish(rt, deployed("deploy-failures", 2, by="not-a-uuid", manifest=again))
    (two,) = (await listed(client, ada, state="draft"))["apps"]
    assert (two["id"], two["version"], two["title"], two["type"], two["roles"], two["submitted_by"]) == (
        one["id"],
        2,
        "Deploy failures v2",
        "page",
        ["sre"],
        None,
    )


async def test_the_review_goes_down_the_link_and_the_welcome_carries_the_catalogue(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine, "Enterprise")
    bob = await member(engine, ada.org_id)
    rt = await self_runtime(engine, ada, HOST)
    await publish(rt, deployed("deploy-failures", manifest=manifest(roles=["sre"])))
    (draft,) = (await listed(client, ada, state="draft"))["apps"]
    path = f"/v1/apps/{draft['id']}"
    refused = await client.post(f"{path}/approve", headers=bob.headers)
    assert (refused.status_code, refused.json()["error"]["reason"]) == (403, "reviewer")
    async with holding(redis, rt.id) as sent:
        approved = await client.post(f"{path}/approve", headers=ada.headers)
        assert approved.status_code == 200, approved.text
        told = await sent()  # between processes, in protocol 3's names
    assert (told["type"], told["program"], told["version"], told["state"], told["roles"]) == (
        "app",
        "deploy-failures",
        1,
        "approved",
        ["sre"],
    )
    body = approved.json()
    assert (body["state"], body["reviewed_by"]["id"], body["reviewed_at"] is not None) == (
        "approved",
        str(ada.user_id),
        True,
    )
    assert (await client.post(f"{path}/approve", headers=ada.headers)).status_code == 409  # already
    await with_reviewers(engine, ada.org_id, ["sre"])
    async with server() as srv, connect(srv, rt.token) as ws:  # a runtime away for the review: its welcome catches up
        await ws.send_json(hello(rt))
        welcome = await ws.receive_json(timeout=WAIT)
    assert welcome["apps"] == [
        {
            "type": "app",
            "id": welcome["apps"][0]["id"],
            "program": "deploy-failures",
            "version": 1,
            "state": "approved",
            "roles": ["sre"],
        }
    ]
    assert welcome["reviewers"] == ["sre"] and "artifacts" not in welcome
    rejected = await client.post(
        f"{path}/reject", json={"reason": "Not yet: the numbers are wrong."}, headers=ada.headers
    )
    assert (rejected.status_code, rejected.json()["state"], rejected.json()["reason"]) == (
        200,
        "rejected",
        "Not yet: the numbers are wrong.",
    )
    assert (await client.post(f"{path}/reject", json={"reason": " "}, headers=ada.headers)).status_code == 422
    assert (await client.post(f"{path}/reject", json={"reason": "x"}, headers=ada.headers)).status_code == 409
    assert (await client.post(f"{path}/approve", headers=ada.headers)).json()["state"] == "approved"
    retired = await client.post(f"{path}/retire", headers=ada.headers)
    assert retired.json()["state"] == "retired"
    assert (await client.post(f"{path}/retire", headers=ada.headers)).status_code == 409
    assert (await client.post(f"{path}/approve", headers=ada.headers)).status_code == 409  # retired stays retired
    assert (await listed(client, ada, state="retired"))["total"] == 1


@pytest.mark.parametrize(("protocol", "one", "many"), [(2, "artifact", "artifacts"), (3, "app", "apps")])
async def test_a_rrotor_hears_the_catalogue_in_the_names_of_its_protocol(
    engine: AsyncEngine, protocol: int, one: str, many: str
) -> None:
    ada = await person(engine, "Enterprise")
    rt = await self_runtime(engine, ada, HOST)
    await publish(rt, deployed("deploy-failures", manifest=manifest(roles=["sre"])))
    other = {"artifacts": "apps", "apps": "artifacts"}[many]
    async with server() as srv, server() as elsewhere, connect(srv, rt.token) as ws:
        await ws.send_json(hello(rt, protocol=protocol))
        welcome = await ws.receive_json(timeout=WAIT)
        assert welcome["type"] == "welcome" and welcome["accepted"] is True and other not in welcome
        assert [(a["type"], a["program"], a["state"]) for a in welcome[many]] == [(one, "deploy-failures", "draft")]
        (draft,) = (await listed(srv.http, ada, state="draft"))["apps"]
        path = f"/v1/apps/{draft['id']}"
        assert (await srv.http.post(f"{path}/approve", headers=ada.headers)).status_code == 200  # this process's link
        told = await receive(ws, one)
        assert (told["program"], told["version"], told["state"]) == ("deploy-failures", 1, "approved")
        assert told["roles"] == ["sre"] and "artifacts" not in told and "apps" not in told
        reason = {"reason": "The numbers are wrong."}
        rejected = await elsewhere.http.post(f"{path}/reject", json=reason, headers=ada.headers)  # relayed from another
        assert rejected.status_code == 200, rejected.text
        assert (await receive(ws, one))["state"] == "rejected"


async def test_members_see_approved_apps_their_roles_allow_searched_filtered_and_paged(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    sre = await member(engine, ada.org_id)
    fin = await member(engine, ada.org_id)
    await with_groups(engine, sre, ["sre", "everyone"])
    rt = await local_runtime(engine, ada)
    apps = [
        ("deploy-failures", "Deploy failures", ["sre"], "dashboard"),
        ("ledger", "Finance ledger", ["finance", "admin"], "doc"),
        ("welcome-board", "Welcome board", [], None),
    ]
    for name, title, roles, type in apps:
        said = {**manifest(title, roles, type=type), "name": name, "description": f"The {title.lower()}."}
        await publish(rt, deployed(name, manifest=said))
    for draft in (await listed(client, ada, state="draft", per_page=100))["apps"]:
        assert (await client.post(f"/v1/apps/{draft['id']}/approve", headers=ada.headers)).status_code == 200
    assert sorted((a["title"], a["type"]) for a in (await listed(client, ada))["apps"]) == [
        ("Deploy failures", "dashboard"),
        ("Finance ledger", "doc"),
        ("Welcome board", "page"),
    ]
    assert sorted(a["title"] for a in (await listed(client, sre))["apps"]) == ["Deploy failures", "Welcome board"]
    assert [a["title"] for a in (await listed(client, fin))["apps"]] == ["Welcome board"]
    found = await listed(client, sre, q="DEPLOY")
    assert [a["title"] for a in found["apps"]] == ["Deploy failures"] and found["total"] == 1
    assert found["apps"][0]["url"] == "http://127.0.0.1:7777/apps/deploy-failures/"
    assert found["apps"][0]["runtime_name"] == "local"
    assert [a["title"] for a in (await listed(client, ada, type="dashboard"))["apps"]] == ["Deploy failures"]
    assert [a["title"] for a in (await listed(client, sre, type="doc"))["apps"]] == []  # not theirs
    assert (await listed(client, ada, type="page", q="welcome"))["total"] == 1
    assert (await client.get("/v1/apps", params={"type": "poster"}, headers=ada.headers)).status_code == 422
    first = await listed(client, ada, per_page=2, page=1)
    second = await listed(client, ada, per_page=2, page=2)
    assert (len(first["apps"]), len(second["apps"]), second["total"]) == (2, 1, 3)
    assert (await client.get("/v1/apps", params={"per_page": 0}, headers=ada.headers)).status_code == 422
    ledger = next(a for a in (await listed(client, ada))["apps"] if a["name"] == "ledger")
    assert (await client.get(f"/v1/apps/{ledger['id']}", headers=sre.headers)).status_code == 404
    assert (await client.get(f"/v1/apps/{ledger['id']}", headers=fin.headers)).status_code == 404
    await with_groups(engine, fin, ["finance"])
    assert (await client.get(f"/v1/apps/{ledger['id']}", headers=fin.headers)).json()["title"] == "Finance ledger"


async def test_a_reviewer_groups_member_reviews_and_the_connector_offers_the_same(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    pat = await member(engine, ada.org_id)
    await with_groups(engine, pat, ["release-managers"])
    await with_reviewers(engine, ada.org_id, ["release-managers"])
    rt = await self_runtime(engine, ada, HOST)
    await publish(rt, deployed("deploy-failures"))
    _, as_pat = await granted(engine, pat)
    me = await tool(client, as_pat, "whoami")
    assert (me["structuredContent"]["groups"], me["structuredContent"]["reviewer"]) == (["release-managers"], True)
    drafts = await tool(client, as_pat, "apps", state="draft")
    assert drafts["isError"] is False and drafts["structuredContent"]["total"] == 1
    assert drafts["content"][0]["text"].startswith(
        "1 draft app, page 1.\nDeploy failures (page) v1 on Acme, draft, by a deploy"
    )
    draft_id = drafts["structuredContent"]["apps"][0]["id"]
    assert (await tool(client, as_pat, "apps"))["content"][0]["text"] == "No approved apps."
    assert (await tool(client, as_pat, "apps", state="draft", type="dashboard"))["structuredContent"]["total"] == 0
    assert (await tool(client, as_pat, "apps", type="poster"))["isError"]
    rejected = await tool(client, as_pat, "app_reject", app_id=draft_id, reason="Needs a title.")
    assert rejected["content"][0]["text"] == "Deploy failures v1 is rejected: Needs a title."
    approved = await tool(client, as_pat, "app_approve", app_id=draft_id)
    assert approved["content"][0]["text"] == f"Deploy failures v1 is approved: {HOST}/apps/deploy-failures/"
    shown = await tool(client, as_pat, "apps", q="deploy")
    assert shown["content"][0]["text"].splitlines()[0] == "1 approved app, page 1."
    retired = await tool(client, as_pat, "app_retire", app_id=draft_id)
    assert retired["content"][0]["text"] == "Deploy failures is retired."
    _, as_stranger = await granted(engine, await member(engine, ada.org_id))
    refused = await tool(client, as_stranger, "app_approve", app_id=draft_id)
    assert refused["isError"] and refused["structuredContent"]["error"]["code"] == "E_FORBIDDEN"
    for old in ("artifacts", "artifact_approve"):  # the first cut's names are gone, not aliased
        assert (await rpc(client, as_pat, "tools/call", name=old, arguments={}))["error"]["code"] == -32602


async def test_an_app_is_its_orgs_alone_and_goes_with_its_runtime(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine, "Enterprise"), await person(engine, "Enterprise")
    rt = await self_runtime(engine, ada, HOST)
    await publish(rt, deployed("deploy-failures"))
    (draft,) = (await listed(client, ada, state="draft"))["apps"]
    assert (await listed(client, eve, state="draft"))["apps"] == []
    assert (await client.post(f"/v1/apps/{draft['id']}/approve", headers=eve.headers)).status_code == 404
    gone = await client.delete(f"/v1/runtimes/self/{rt.id}", headers=ada.headers)
    assert gone.status_code == 204
    assert (await listed(client, ada, state="draft"))["apps"] == []


def test_roles_types_and_urls() -> None:
    assert (
        ops.allowed([], "member", [])
        and ops.allowed(["admin"], "admin", [])
        and ops.allowed(["sre"], "member", ["sre"])
    )
    assert not ops.allowed(["sre"], "member", ["finance"])
    assert ops.app_url("self", HOST, "x") == f"{HOST}/apps/x/" and ops.app_url("local", None, "x").startswith(
        "http://127"
    )
    assert catalogue.subject_of(None) is None and catalogue.subject_of("nope") is None
    assert catalogue.subject_of(str(uuid.UUID(int=1))) == uuid.UUID(int=1)
    assert (
        catalogue.roles_in({"roles": [" SRE ", "sre", 3, ""]}) == ["sre"] and catalogue.roles_in({"roles": "x"}) == []
    )
    assert catalogue.type_of({}) == "page" and catalogue.type_of({"type": "deck"}) == "deck"
    assert catalogue.type_of({"type": "Dashboard"}) == "page" and catalogue.type_of({"type": 3}) == "page"
