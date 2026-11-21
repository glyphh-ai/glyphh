"""The hosted bots under test: the server with an Anthropic key and Pipedream set up, Pipedream faked at the HTTP
layer and Claude faked in the bots service (app.state.bots.claude)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from tests.bots.fakes import PROJECT, FakeClaude, FakePipedream, account, pipedream_http, reply, text
from tests.conftest import SETTINGS, _client
from tests.db.helpers import Person

BOTS: Settings = SETTINGS.model_copy(
    update={
        "anthropic_api_key": "sk-ant-test-not-a-real-key",
        "pipedream_client_id": "pd-client",
        "pipedream_client_secret": "pd-secret",
        "pipedream_project_id": PROJECT,
    }
)


@dataclass
class Served:
    http: httpx.AsyncClient
    app: FastAPI
    pd: FakePipedream
    claude: FakeClaude

    async def settled(self) -> None:
        await self.app.state.bots.wait()


async def serve(settings: Settings, pd: FakePipedream) -> AsyncIterator[Served]:
    app = create_app(settings, http=pipedream_http(pd))
    async for c in _client(app):
        claude = FakeClaude(reply(text("Done.")))
        app.state.bots.claude = claude
        yield Served(c, app, pd, claude)


@pytest.fixture
async def served(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakePipedream()):
        yield s


async def made_bot(s: Served, who: Person, **over: Any) -> dict[str, Any]:
    body = {"name": "Inbox Cat", "summary": "Sorts mail", "instructions": "Answer the mail.", **over}
    res = await s.http.post("/v1/bots", json=body, headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())


async def connected(s: Served, who: Person, account_id: str = "apn_1") -> dict[str, Any]:
    """A Gmail account signed in at Pipedream and synced: the org's connection."""
    s.pd.accounts.append(account(account_id))
    res = await s.http.post("/v1/connections/sync", headers=who.headers)
    assert res.status_code == 200, res.text
    return next(c for c in res.json()["connections"] if c["account_id"] == account_id)
