"""The hosted bots under test: the server with Glyphh's Anthropic key and Pipedream set up, Pipedream faked at the HTTP
layer, and the bots service given a fake Ada (app.state.bots.ada_for), a fake Claude behind the SDK's ApiClaude for
the bot maker (claude_for), and a fake agent in place of the Agent SDK's turn (agent: tests/bots/agents.py); a key is
tried with Anthropic by a fake too (check_key). INBOX is a bot that finds the mail, has Ada decide which is worth
answering, and sends a reply once the person says yes."""

import copy
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from glyphh.bots import ApiClaude
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.ops.bots.access import WithEffort
from tests.bots.agents import FakeAgent
from tests.bots.fakes import PROJECT, FakeAda, FakeAnthropic, FakePipedream, account, pipedream_http
from tests.conftest import SETTINGS, _client
from tests.db.helpers import Person, person

BOTS: Settings = SETTINGS.model_copy(
    update={
        "anthropic_api_key": "sk-ant-glyphh-test-key",
        "pipedream_client_id": "pd-client",
        "pipedream_client_secret": "pd-secret",
        "pipedream_project_id": PROJECT,
    }
)
WORTH_SPEC: dict[str, Any] = {
    "name": "worth",
    "layers": [{"name": "m", "segments": [{"name": "s", "roles": [
        {"name": "subject", "text_encoding": "bag_of_words"},
        {"name": "id", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"ask_below": 0.7},
}  # fmt: skip
INBOX: dict[str, Any] = {
    "seed": {"personality": ["Short and kind."]},
    "gates": {
        "worth": {
            "case": {"m": {"s": {"subject": "$item.subject", "id": "$item.id"}}},
            "outcomes": ["answer", "skip"],
            "question": "Worth answering?",
            "spec": WORTH_SPEC,
        }
    },
}
TOOLS: list[str] = ["gmail-find-email", "gmail-send-email"]
FIND, SEND, DECIDE, ASK = "gmail_find_email", "gmail_send_email", "decide", "ask_person"


def asks(items: list[dict[str, Any]], decision: str = "worth") -> tuple[str, dict[str, Any]]:
    """The agent asking the person about a decision's items (its own question, from the decision)."""
    return (ASK, {"question": "", "decision": decision, "items": items})


@dataclass
class Served:
    http: httpx.AsyncClient
    app: FastAPI
    pd: FakePipedream
    ada: FakeAda
    claude: FakeAnthropic
    agent: FakeAgent

    async def settled(self) -> None:
        await self.app.state.bots.wait()


def faked(app: FastAPI, ada: FakeAda, claude: FakeAnthropic, agent: FakeAgent) -> None:
    bots = app.state.bots

    def ada_for(key: str) -> FakeAda:
        ada.keys.append(key)
        return ada

    def claude_for(key: str, model: str, effort: str | None = None) -> ApiClaude:
        claude.keys.append(key)
        return ApiClaude(client=WithEffort(claude, effort), model=model)  # as goes._claude wraps the real client

    async def check_key(key: str) -> str | None:
        return "Anthropic does not take that key." if key.endswith("-bad") else None

    bots.ada_for, bots.claude_for, bots.check_key, bots.agent = ada_for, claude_for, check_key, agent


async def serve(settings: Settings, pd: FakePipedream) -> AsyncIterator[Served]:
    app = create_app(settings, http=pipedream_http(pd))
    async for c in _client(app):
        ada, claude, agent = FakeAda(), FakeAnthropic("Happy to, see you Friday."), FakeAgent()
        faked(app, ada, claude, agent)
        yield Served(c, app, pd, ada, claude, agent)


@pytest.fixture
async def served(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakePipedream()):
        yield s


@pytest.fixture
async def ana(engine: AsyncEngine) -> Person:
    return await person(engine)


def inbox(**over: Any) -> dict[str, Any]:
    return {**copy.deepcopy(INBOX), **over}


async def connected(s: Served, who: Person, account_id: str = "apn_1", allow: bool = True) -> dict[str, Any]:
    """A Gmail account signed in at Pipedream and synced: the org's connection, both its tools allowed (unless not:
    then neither is set)."""
    s.pd.accounts.append(account(account_id))
    res = await s.http.post("/v1/connections/sync", headers=who.headers)
    assert res.status_code == 200, res.text
    made = next(c for c in res.json()["connections"] if c["account_id"] == account_id)
    if allow:
        modes = {"permissions": {t: "allow" for t in TOOLS}}
        res = await s.http.put(f"/v1/connections/{made['id']}/permissions", json=modes, headers=who.headers)
        assert res.status_code == 200, res.text
        made = res.json()
    return dict(made)


async def made_bot(s: Served, who: Person, **over: Any) -> dict[str, Any]:
    """The inbox bot, its Gmail connection scoped to both tools, unless `over` says otherwise."""
    if "connections" not in over and "spec" not in over:
        gmail = await connected(s, who)
        over["connections"] = [{"connection_id": gmail["id"], "tools": TOOLS}]
    body = {
        "name": "Inbox Cat",
        "summary": "Answers the mail worth answering",
        "instructions": "You are Inbox Cat. Find the mail, decide what is worth answering, write short, kind replies.",
        "spec": inbox(),
        "skills": {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph, no sign-off.\n"},
        "task": "Answer the mail worth answering.",
        "examples": ["Anything worth answering?"],
        **over,
    }
    res = await s.http.post("/v1/bots", json=body, headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())


async def ran(s: Served, who: Person, slug: str, said: str = "") -> dict[str, Any]:
    """A run of the bot started with `said`, as it stands once nothing of it is going."""
    res = await s.http.post(f"/v1/bots/{slug}/runs", json={"input": said}, headers=who.headers)
    assert res.status_code == 202, res.text
    await s.settled()
    return await run_of(s, who, res.json()["id"])


async def run_of(s: Served, who: Person, run_id: str) -> dict[str, Any]:
    res = await s.http.get(f"/v1/bot-runs/{run_id}", headers=who.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


async def answered(s: Served, who: Person, run_id: str, answer: Any) -> dict[str, Any]:
    """The waiting run answered, as it stands once nothing of it is going."""
    res = await s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": answer}, headers=who.headers)
    assert res.status_code == 202, res.text
    await s.settled()
    return await run_of(s, who, run_id)
