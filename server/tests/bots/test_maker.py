"""Create with AI: the bot maker's turns (a question, a draft checked and scoped, a wrong draft sent back once), a
mascot drawn and made safe, kept on a bot, and both through the connector."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import maker
from tests.bots.conftest import BOTS, TOOLS, Served, connected, inbox, serve
from tests.bots.fakes import FakePipedream
from tests.connector import granted, tool
from tests.db.helpers import person

SKILLS = {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph.\n"}
CAT = '<svg viewBox="0 0 200 200"><path d="M10 10 L90 90 Z" fill="#0b0a0f" stroke="white" stroke-width="12"/></svg>'


def drafted(reply: str = "Here it is.", **over: Any) -> str:
    draft = {
        "name": "Inbox Cat",
        "summary": "Answers the mail worth answering",
        "look": {"head": "tall", "eye": "heart", "hat": "no"},
        "instructions": "You are Inbox Cat. Short, kind replies.",
        "model": "claude-sonnet-5-5",
        "spec": inbox(),
        "skills": SKILLS,
        "apps": [{"app": "gmail", "tools": TOOLS}],
        **over,
    }
    return "Sure.\n" + json.dumps({"reply": reply, "draft": draft})


def said(*texts: str) -> dict[str, Any]:
    return {"messages": [{"role": "user" if i % 2 == 0 else "assistant", "content": t} for i, t in enumerate(texts)]}


async def test_the_maker_asks_then_drafts_a_checked_bot_scoped_to_the_orgs_connections(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    served.claude.texts = ['{"reply": "What should it do with the mail?", "draft": null}', drafted()]
    res = await served.http.post("/v1/bots/draft", json=said("A bot for my inbox"), headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "reply": "What should it do with the mail?",
        "draft": None,
        "problems": [],
        "missing_apps": [],
    }
    sent = served.claude.requests[0]
    assert "Glyphh's bot maker" in sent["system"] and "none yet" in sent["system"] and "$id.path" in sent["system"]
    assert sent["model"] == "claude-opus-5-5" and "Person: A bot for my inbox" in sent["messages"][0]["content"]

    res = await served.http.post(
        "/v1/bots/draft", json=said("A bot for my inbox", "What?", "Reply"), headers=ada.headers
    )
    got = res.json()
    assert got["problems"] == [] and got["missing_apps"] == ["gmail"] and got["draft"]["connections"] == []
    assert got["draft"]["look"] == {"head": "tall", "eye": "heart"} and got["draft"]["model"] == "claude-sonnet-5-5"

    gmail = await connected(served, ada)
    served.claude.texts = [drafted(model="gpt-9")]
    body = {**said("Reply"), "draft": {"mascot": CAT}}
    got = (await served.http.post("/v1/bots/draft", json=body, headers=ada.headers)).json()
    assert got["missing_apps"] == [] and got["draft"]["model"] == "claude-opus-5-5" and got["draft"]["mascot"] == CAT
    assert got["draft"]["connections"] == [{"connection_id": gmail["id"], "tools": TOOLS}]
    assert (
        "gmail" in served.claude.requests[-1]["system"]
        and "draft so far" in served.claude.requests[-1]["messages"][0]["content"]
    )
    made = await served.http.post(
        "/v1/bots", json={k: v for k, v in got["draft"].items() if k != "apps"}, headers=ada.headers
    )
    assert made.status_code == 201, made.text
    assert made.json()["mascot"].startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">')


async def test_a_wrong_draft_is_sent_back_once_and_what_is_still_wrong_is_said(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    wrong = drafted(apps=[])
    served.claude.texts = [wrong, drafted("Fixed it.")]
    got = (await served.http.post("/v1/bots/draft", json=said("Inbox"), headers=ada.headers)).json()
    assert got["reply"] == "Fixed it." and got["problems"] == []
    assert "fix them all" in served.claude.requests[-1]["messages"][0]["content"]

    served.claude.texts = [wrong, "I cannot."]
    got = (await served.http.post("/v1/bots/draft", json=said("Inbox"), headers=ada.headers)).json()
    assert got["reply"] == "Here it is." and "gmail-find-email is neither fetch nor a tool" in got["problems"][0]

    ada = await person(engine)  # the meter lets an org's plan 5 calls a second: another org for the rest
    served.claude.texts = [drafted(instructions=None, name="9")]
    got = (await served.http.post("/v1/bots/draft", json=said("Inbox"), headers=ada.headers)).json()
    assert got["draft"] is None and got["problems"] == ["instructions: Input should be a valid string"]

    served.claude.texts = [drafted(name="99"), drafted(name="99")]
    got = (await served.http.post("/v1/bots/draft", json=said("Inbox"), headers=ada.headers)).json()
    assert got["problems"] == ["A bot's name needs a letter."]


async def test_the_maker_says_when_claude_cannot_answer(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    served.claude.fail = RuntimeError("overloaded")
    res = await served.http.post("/v1/bots/draft", json=said("Inbox"), headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "claude"
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": ""}), FakePipedream()):
        res = await s.http.post("/v1/bots/mascot", json={"prompt": "a cat"}, headers=ada.headers)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "anthropic_off"


def test_a_reply_that_is_not_the_json_asked_for_is_the_reply_alone() -> None:
    assert maker.parsed("Just words.") == ("Just words.", None)
    assert maker.parsed("{not json}") == ("{not json}", None)
    assert maker.parsed('["a"]') == ('["a"]', None)
    assert maker.parsed('{"reply": "Hi", "draft": "x"}') == ("Hi", None)


async def test_a_mascot_is_drawn_made_safe_and_kept_on_a_bot(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    served.claude.texts = [f"Here you go:\n```svg\n{CAT.replace('/>', ' onclick="x()"/><script>x()</script>')}\n```"]
    res = await served.http.post("/v1/bots/mascot", json={"prompt": "a cat with a bow"}, headers=ada.headers)
    assert res.status_code == 200, res.text
    drawn = res.json()["mascot"]
    assert "script" not in drawn and "onclick" not in drawn and 'fill="#0b0a0f" stroke="#ffffff"' in drawn
    assert "Spike" in served.claude.requests[-1]["system"]
    served.claude.texts = ["No."]
    res = await served.http.post("/v1/bots/mascot", json={"prompt": "nothing"}, headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "mascot"

    body = {"name": "Plain", "instructions": "Be kind.", "spec": {"loop": [{"id": "a", "agent": "Hi"}]}}
    made = await served.http.post("/v1/bots", json={**body, "mascot": drawn}, headers=ada.headers)
    assert made.status_code == 201 and made.json()["mascot"] == drawn
    bad = await served.http.patch("/v1/bots/plain", json={"mascot": "<svg><!ENTITY x></svg>"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "mascot"
    gone = await served.http.patch("/v1/bots/plain", json={"mascot": ""}, headers=ada.headers)
    assert gone.json()["mascot"] == ""


async def test_the_maker_and_the_mascot_through_the_connector(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    served.claude.texts = [drafted(apps=[]), drafted(apps=[])]
    got = await tool(served.http, auth, "bot_draft", messages=[{"role": "user", "content": "Inbox"}])
    text = got["content"][0]["text"]
    assert got["isError"] is False and "Still wrong: step mail" in text and "Connect first" not in text
    served.claude.texts = [drafted()]
    got = await tool(served.http, auth, "bot_draft", messages=[{"role": "user", "content": "Inbox"}])
    assert "Connect first: gmail (connection_link)." in got["content"][0]["text"]
    served.claude.texts = [CAT]
    drawn = await tool(served.http, auth, "bot_mascot", prompt="a cat")
    assert drawn["structuredContent"]["mascot"].endswith("</svg>") and "bot_create" in drawn["content"][0]["text"]
