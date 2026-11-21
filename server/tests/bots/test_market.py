"""The bots marketplace and finding a bot: templates Glyphh ships, searched, read and copied into an org (refused
until the apps it needs are connected), and the org's bots searched by their words."""

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import templates
from tests.bots.conftest import Served, connected, made_bot
from tests.bots.test_runs import answered, started
from tests.connector import granted, tool
from tests.db.helpers import person


async def test_a_template_is_searched_read_and_installed_once_its_apps_are_connected(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    listed = (await served.http.get("/v1/bot-templates?q=inbox gmail", headers=ada.headers)).json()["templates"]
    assert [t["slug"] for t in listed] == ["inbox-triage"] and listed[0]["gates"] == ["worth"]
    assert (await served.http.get("/v1/bot-templates?q=payroll", headers=ada.headers)).json()["templates"] == []
    one = (await served.http.get("/v1/bot-templates/inbox-triage", headers=ada.headers)).json()
    assert one["apps"] == ["gmail"] and one["tools"] == ["gmail-find-email", "gmail-send-email"]
    assert (await served.http.get("/v1/bot-templates/nope", headers=ada.headers)).status_code == 404
    res = await served.http.post("/v1/bot-templates/inbox-triage/install", json={}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["apps"] == ["gmail"]
    gmail = await connected(served, ada)
    res = await served.http.post("/v1/bot-templates/inbox-triage/install", json={"name": "Mail"}, headers=ada.headers)
    assert res.status_code == 201, res.text
    bot = res.json()
    assert (bot["slug"], bot["model"], bot["gate_models"][0]) == ("mail", "claude-sonnet-5-5", "bot-mail-gate-worth")
    assert bot["connections"] == [{"connection_id": gmail["id"], "app": "gmail", "app_name": "Gmail",
                                   "tools": ["gmail-find-email", "gmail-send-email"]}]  # fmt: skip
    grace = await person(engine)  # another org sees neither ada's connection nor it to install with
    modes = {"permissions": {"gmail-send-email": "allow"}}
    res = await served.http.put(f"/v1/connections/{gmail['id']}/permissions", json=modes, headers=grace.headers)
    assert res.status_code == 404
    res = await served.http.post("/v1/bot-templates/inbox-triage/install", json={}, headers=grace.headers)
    assert res.status_code == 422


async def test_the_marketplace_and_the_orgs_bots_through_the_connector(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    found = await tool(served.http, auth, "bot_templates", q="inbox")
    assert (
        found["content"][0]["text"].startswith("Inbox Triage (inbox-triage): ")
        and "needs gmail" in found["content"][0]["text"]
    )
    assert (await tool(served.http, auth, "bot_templates", q="zzz"))["content"][0]["text"] == "No such bot template."
    read = await tool(served.http, auth, "bot_template", slug="inbox-triage")
    assert "Tools: gmail-find-email, gmail-send-email" in read["content"][0]["text"]
    await connected(served, ada)
    added = await tool(served.http, auth, "bot_template_install", slug="inbox-triage")
    assert added["content"][0]["text"].startswith("Added Inbox Triage (inbox-triage)")
    await made_bot(served, ada)
    assert "Inbox Cat" in (await tool(served.http, auth, "bots", q="cat"))["content"][0]["text"]
    hits = (await tool(served.http, auth, "bots", q="digest inbox"))["structuredContent"]["bots"]
    assert [b["slug"] for b in hits] == ["inbox-triage"]
    listed = (await served.http.get("/v1/bots?q=50%_", headers=ada.headers)).json()["bots"]
    assert listed == []  # its words are words, never patterns
    assert templates.listing(None).templates[0].slug == "inbox-triage"


async def test_an_installed_template_runs_its_loop_end_to_end(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await connected(served, ada)
    made = await served.http.post("/v1/bot-templates/inbox-triage/install", json={}, headers=ada.headers)
    assert made.status_code == 201, made.text
    assert made.json()["connections"][0]["tools"] == ["gmail-find-email", "gmail-send-email"], made.text
    run = await started(served, ada, given="me@navy.test", slug="inbox-triage")
    assert run["question"] is not None, (run["status"], run["error"], run["log"])
    assert run["question"]["options"] == ["read", "skip"], run
    run = await answered(served, ada, run, "1=read 2=skip")
    assert "email you the digest" in run["question"]["question"], run
    run = await answered(served, ada, run, "yes")
    assert run["status"] == "done", run["error"]
    sent = served.pd.runs[-1]["configured_props"]
    assert sent["to"] == ["me@navy.test"] and sent["body"] == "Happy to, see you Friday."
    assert "Lunch on Friday?" in served.claude.requests[0]["messages"][0]["content"]
    assert "You won!" not in served.claude.requests[0]["messages"][0]["content"]
