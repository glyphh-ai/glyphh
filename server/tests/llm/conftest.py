"""The Glyphh-hosted models under test (docs/specs/tokens.md): the server with Ada Cloud and GLYPHH_LLM on, `ada.test`
its Ada host (inference, API keys) and `api.test` the account API's, the inference server and Stripe faked at the HTTP
layer."""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.llm import ledger
from glyphh_server.models import LlmBalance
from glyphh_server.ops.billing.signature import sign
from tests.ada.conftest import ADA, HOST, ada, key_for, vector  # noqa: F401 (ada, vector: fixtures)
from tests.conftest import WEBHOOK_SECRET, _client
from tests.db.helpers import Person, person
from tests.fakes import INFERENCE_HOST, FakeInference, FakeStripe, fake_http

API: str = "http://api.test"
HOSTED: Settings = ADA.model_copy(
    update={"llm": True, "inference_url": f"http://{INFERENCE_HOST}/", "inference_key": "ik_test"}
)
MODEL: str = "adal-34b-1-0"
ASK: dict[str, Any] = {"model": MODEL, "messages": [{"role": "user", "content": "Hi"}]}


@pytest.fixture
def inference() -> FakeInference:
    return FakeInference()


async def hosted_client(settings: Settings, stripe: FakeStripe, inference: FakeInference) -> AsyncIterator[Any]:
    async for c in _client(create_app(settings, http=fake_http(stripe, inference=inference))):
        c.base_url = httpx.URL(f"http://{HOST}")
        yield c


@pytest.fixture
async def hosted(
    engine: AsyncEngine,
    vector: None,  # noqa: F811
    stripe: FakeStripe,
    inference: FakeInference,
) -> AsyncIterator[httpx.AsyncClient]:
    async for c in hosted_client(HOSTED, stripe, inference):
        yield c


async def org_with_key(engine: AsyncEngine, hosted: httpx.AsyncClient, plan: str = "Free") -> tuple[Person, Any]:
    who = await person(engine, plan)
    return who, await key_for(hosted, who)


async def holding(
    engine: AsyncEngine, org_id: Any, micros: int = 0, tokens: int = 0, period: str | None = None
) -> None:
    """The org's balance and this month's allowance used, as they would be after its requests and top-ups."""
    async with engine.begin() as conn:
        await conn.execute(upsert(LlmBalance).values(org_id=org_id).on_conflict_do_nothing())
        values = {"micros": micros, "tokens": tokens, "period": period or ledger.period()}
        await conn.execute(update(LlmBalance).where(LlmBalance.org_id == org_id).values(**values))


async def billing(hosted: httpx.AsyncClient, who: Person) -> dict[str, Any]:
    res = await hosted.get(f"{API}/v1/billing", headers=who.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


async def webhook(client: httpx.AsyncClient, kind: str, obj: dict[str, Any]) -> httpx.Response:
    body = json.dumps({"id": "evt_1", "type": kind, "data": {"object": obj}}).encode()
    headers = {"stripe-signature": sign(WEBHOOK_SECRET, body, int(time.time())), "content-type": "application/json"}
    return await client.post(f"{API}/v1/stripe/webhook", content=body, headers=headers)


def paid_session(org_id: Any, cents: int, session: str, status: str = "paid") -> dict[str, Any]:
    meta = {"org_id": str(org_id), "kind": "llm_topup"}
    values = {"id": session, "mode": "payment", "payment_status": status, "currency": "usd", "amount_total": cents}
    return values | {"client_reference_id": str(org_id), "customer": None, "metadata": meta}
