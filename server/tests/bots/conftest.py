"""The hosted bots under test: the server with Glyphh's Anthropic key and Pipedream set up, Pipedream faked at the HTTP
layer, and the bots service given a fake Ada (app.state.bots.ada_for) and a fake Claude behind the SDK's ApiClaude
(claude_for); a key is tried with Anthropic by a fake too (check_key). INBOX is a bot that finds the mail, lets a
gate pick the mail worth answering, drafts a reply and sends it once the person says yes."""

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
from tests.bots.fakes import PROJECT, FakeAda, FakeAnthropic, FakePipedream, account, pipedream_http
from tests.conftest import SETTINGS, _client
from tests.db.helpers import Person

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
    "touches": "sends",
    "seed": {"personality": ["Short and kind."]},
    "gates": {
        "worth": {
            "case": {"m": {"s": {"subject": "$item.subject", "id": "$item.id"}}},
            "outcomes": ["answer", "skip"],
            "question": "Worth answering?",
            "spec": WORTH_SPEC,
        }
    },
    "loop": [
        {"id": "mail", "run": "gmail-find-email", "input": {"q": "$input"}},
        {"id": "worth", "gate": "worth", "each": "$mail.ret", "label": "subject", "key": "id",
         "on": {"empty:answer": "end"}},
        {"id": "draft", "agent": "Write one reply to: $worth.answer", "skill": "replies"},
        {"id": "send", "run": "gmail-send-email", "approval": "send the reply",
         "input": {"to": ["grace@navy.test"], "subject": "Re", "body": "$draft"}},
    ],
}  # fmt: skip
TOOLS: list[str] = ["gmail-find-email", "gmail-send-email"]


@dataclass
class Served:
    http: httpx.AsyncClient
    app: FastAPI
    pd: FakePipedream
    ada: FakeAda
    claude: FakeAnthropic

    async def settled(self) -> None:
        await self.app.state.bots.wait()


def faked(app: FastAPI, ada: FakeAda, claude: FakeAnthropic) -> None:
    bots = app.state.bots

    def ada_for(key: str) -> FakeAda:
        ada.keys.append(key)
        return ada

    def claude_for(key: str, model: str, effort: str | None = None) -> ApiClaude:
        claude.keys.append(key)
        return ApiClaude(client=WithEffort(claude, effort), model=model)  # as goes._claude wraps the real client

    async def check_key(key: str) -> str | None:
        return "Anthropic does not take that key." if key.endswith("-bad") else None

    bots.ada_for, bots.claude_for, bots.check_key = ada_for, claude_for, check_key


async def serve(settings: Settings, pd: FakePipedream) -> AsyncIterator[Served]:
    app = create_app(settings, http=pipedream_http(pd))
    async for c in _client(app):
        ada, claude = FakeAda(), FakeAnthropic("Happy to, see you Friday.")
        faked(app, ada, claude)
        yield Served(c, app, pd, ada, claude)


@pytest.fixture
async def served(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakePipedream()):
        yield s


def inbox(**over: Any) -> dict[str, Any]:
    return {**copy.deepcopy(INBOX), **over}


async def connected(s: Served, who: Person, account_id: str = "apn_1", allow: bool = True) -> dict[str, Any]:
    """A Gmail account signed in at Pipedream and synced: the org's connection, both its tools allowed (unless not:
    then each asks)."""
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
        "instructions": "You are Inbox Cat. Write short, kind replies.",
        "spec": inbox(),
        "skills": {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph, no sign-off.\n"},
        **over,
    }
    res = await s.http.post("/v1/bots", json=body, headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())
