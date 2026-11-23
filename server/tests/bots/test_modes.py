"""A bot's "Before it acts" (docs/specs/bot-agent-loop.md, 5), as a person sets it and its runs then behave: Ask me
first, Follow each app's settings, Act on its own, and a tool its connection denies refused under each; and the voice
a bot speaks in. (The whole table of mode, tool and connection is tests/bots/test_agent_parts.py's.)"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.agents import play
from tests.bots.conftest import FIND, SEND, Served, connected, made_bot, ran
from tests.connector import granted, tool
from tests.db.helpers import Person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
TOOLS: list[str] = ["gmail-find-email", "gmail-send-email"]


async def mode(s: Served, who: Person, value: str) -> Any:
    return await s.http.patch("/v1/bots/inbox-cat", json={"permission_mode": value}, headers=who.headers)


async def allowed(s: Served, who: Person, gmail: str, **modes: str) -> None:
    said = {"permissions": {k.replace("_", "-"): v for k, v in modes.items()}}
    res = await s.http.put(f"/v1/connections/{gmail}/permissions", json=said, headers=who.headers)
    assert res.status_code == 200, res.text


async def sends(s: Served, who: Person) -> dict[str, Any]:
    """A run whose agent reads the mail, then sends a reply; cancelled when it stops to ask."""
    s.agent.script = [play((FIND, {"q": "is:unread"}), (SEND, REPLY), text="Sent.")]
    run = await ran(s, who, "inbox-cat", "Reply to Grace")
    if run["status"] == "needs_input":
        assert (await s.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=who.headers)).status_code == 200
    return run


async def test_the_mode_a_person_sets_is_how_the_bots_runs_ask(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)  # neither tool is set on its connection
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": TOOLS}])
    assert bot["permission_mode"] == "ask" and bot["voice"] == ""
    run = await sends(served, ana)  # Ask me first: reading runs, the action asks
    assert run["status"] == "needs_input" and run["question"]["question"] == "Send Email in Gmail?"
    assert [x["title"] for x in run["steps"]] == ["Find Email"] and len(served.pd.runs) == 1
    await allowed(served, ana, gmail["id"], gmail_send_email="allow")
    assert (await sends(served, ana))["status"] == "done"  # unless its connection allows it
    assert [p["id"] for p in served.pd.runs][1:] == TOOLS

    assert (await mode(served, ana, "connection")).json()["permission_mode"] == "connection"
    assert (await sends(served, ana))["status"] == "done"  # Follow each app's settings: allowed there
    await allowed(served, ana, gmail["id"], gmail_send_email="ask", gmail_find_email="ask")
    run = await sends(served, ana)
    assert run["question"]["question"] == "Find Email in Gmail?" and run["steps"] == []  # even reading, told to ask
    assert (await mode(served, ana, "never")).status_code == 422


async def test_a_bot_that_acts_on_its_own_asks_nothing_but_never_uses_a_denied_tool(
    served: Served, ana: Person
) -> None:
    gmail = await connected(served, ana, allow=False)
    scopes = [{"connection_id": gmail["id"], "tools": TOOLS}]
    bot = await made_bot(served, ana, connections=scopes, permission_mode="auto")
    await allowed(served, ana, gmail["id"], gmail_send_email="ask", gmail_find_email="ask")
    run = await sends(served, ana)  # Act on its own: nothing asks, whatever the connection says of asking
    assert bot["permission_mode"] == "auto" and run["status"] == "done", run["error"]
    assert [p["id"] for p in served.pd.runs] == TOOLS
    await allowed(served, ana, gmail["id"], gmail_send_email="deny")
    run = await sends(served, ana)  # but never a tool its connection denies
    assert run["status"] == "done" and len(served.pd.runs) == 3
    assert [(x["title"], x["ok"]) for x in run["steps"]] == [("Find Email", True), ("Send Email", False)]


async def test_a_bot_speaks_in_one_of_the_listed_voices(served: Served, ana: Person, engine: AsyncEngine) -> None:
    listed = (await served.http.get("/v1/bots/voices", headers=ana.headers)).json()
    assert listed["samples"] is False and listed["voices"][0] == {
        "id": "af_heart", "name": "Heart", "accent": "American", "gender": "female", "default": True,
    }  # fmt: skip
    assert {"bm_george", "bf_emma", "am_michael", "af_bella"} <= {v["id"] for v in listed["voices"]}
    bot = await made_bot(served, ana, voice="bm_george", permission_mode="connection")
    assert (bot["voice"], bot["permission_mode"]) == ("bm_george", "connection")
    res = await served.http.patch("/v1/bots/inbox-cat", json={"voice": "hal_9000"}, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "voice"
    res = await served.http.patch("/v1/bots/inbox-cat", json={"voice": ""}, headers=ana.headers)
    assert res.json()["voice"] == ""
    _, auth = await granted(engine, ana)
    said = await tool(served.http, auth, "bot_voices")
    assert said["content"][0]["text"].startswith("af_heart (American female), ")
