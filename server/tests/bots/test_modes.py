"""A bot's permission mode (which tool steps wait for the person), its voice, and every bot template Glyphh ships
installing once its apps are connected."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import cloud, templates
from tests.bots.conftest import Served, connected, made_bot
from tests.bots.fakes import account
from tests.bots.test_runs import started
from tests.connector import granted, tool
from tests.db.helpers import person


@pytest.mark.parametrize(
    ("mode", "permission", "asks"),
    [
        ("ask", None, True), ("ask", "ask", True), ("ask", "allow", False),
        ("connection", None, False), ("connection", "ask", True), ("connection", "allow", False),
        ("auto", None, False), ("auto", "ask", False), ("auto", "allow", False),
    ],
)  # fmt: skip
def test_the_mode_and_the_connection_say_which_tool_steps_ask(mode: str, permission: str | None, asks: bool) -> None:
    assert cloud.asks(mode, permission) is asks


async def test_a_bot_in_auto_runs_its_tools_without_asking_but_never_a_denied_one(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    gmail = await connected(served, ada, allow=False)  # each tool asks, by the connection
    scopes = [{"connection_id": gmail["id"], "tools": ["gmail-find-email", "gmail-send-email"]}]
    bot = await made_bot(served, ada, connections=scopes)
    assert bot["permission_mode"] == "ask" and bot["voice"] == ""
    run = await started(served, ada)
    assert run["question"]["question"].startswith("mail: use gmail-find-email")
    await served.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
    res = await served.http.patch("/v1/bots/inbox-cat", json={"permission_mode": "auto"}, headers=ada.headers)
    assert res.json()["permission_mode"] == "auto"
    run = await started(served, ada)
    assert run["question"]["question"].startswith("Worth answering?")
    await served.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
    modes = {"permissions": {"gmail-find-email": "deny"}}
    await served.http.put(f"/v1/connections/{gmail['id']}/permissions", json=modes, headers=ada.headers)
    run = await started(served, ada)
    assert run["status"] == "failed" and "blocked on the Gmail connection" in run["error"]
    res = await served.http.patch("/v1/bots/inbox-cat", json={"permission_mode": "never"}, headers=ada.headers)
    assert res.status_code == 422


async def test_a_bot_speaks_in_one_of_the_listed_voices(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    listed = (await served.http.get("/v1/bots/voices", headers=ada.headers)).json()
    assert listed["samples"] is False and listed["voices"][0] == {
        "id": "af_heart", "name": "Heart", "accent": "American", "gender": "female", "default": True,
    }  # fmt: skip
    assert {"bm_george", "bf_emma", "am_michael", "af_bella"} <= {v["id"] for v in listed["voices"]}
    bot = await made_bot(served, ada, voice="bm_george", permission_mode="connection")
    assert (bot["voice"], bot["permission_mode"]) == ("bm_george", "connection")
    res = await served.http.patch("/v1/bots/inbox-cat", json={"voice": "hal_9000"}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "voice"
    res = await served.http.patch("/v1/bots/inbox-cat", json={"voice": ""}, headers=ada.headers)
    assert res.json()["voice"] == ""
    _, auth = await granted(engine, ada)
    said = await tool(served.http, auth, "bot_voices")
    assert said["content"][0]["text"].startswith("af_heart (American female), ")


@pytest.mark.parametrize("slug", sorted(templates.library()))
async def test_every_template_installs_once_its_apps_are_connected(
    slug: str, served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    t = templates.one(slug)
    assert t.gates and t.skills
    for i, app in enumerate(t.apps):
        served.pd.accounts.append(account(f"apn_{i}", {"name_slug": app, "name": app.title(), "img_src": ""}))
    if t.apps:
        res = await served.http.post(f"/v1/bot-templates/{slug}/install", json={}, headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["apps"] == t.apps
        assert (await served.http.post("/v1/connections/sync", headers=ada.headers)).status_code == 200
    res = await served.http.post(f"/v1/bot-templates/{slug}/install", json={}, headers=ada.headers)
    assert res.status_code == 201, res.text
    bot = res.json()
    assert sorted(k for c in bot["connections"] for k in c["tools"]) == sorted(t.tools)
    assert len(bot["gate_models"]) > len(t.gates) and bot["slug"] == slug
