"""The inference server refusing, failing or away: the caller's 400 or a 503, never charged; and the parts on their own
(the stream cut off, the rate, Redis down, the registry's checks)."""

import uuid
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.errors import RateLimited
from glyphh_server.llm import meter, proxy, registry
from glyphh_server.llm.meter import Admitted
from tests.conftest import REDIS_URL
from tests.db.helpers import person
from tests.fakes import FakeInference, FakeStripe
from tests.llm.conftest import API, ASK, HOSTED, MODEL, billing, hosted_client, org_with_key


async def _refused(hosted: httpx.AsyncClient, key: Any, body: dict[str, Any] = ASK) -> tuple[int, dict[str, Any]]:
    res = await hosted.post("/v1/chat/completions", json=body, headers=key)
    return res.status_code, res.json()["error"]


async def test_the_servers_refusals_and_failures_are_never_charged(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted, "Pro")  # 50 calls a second: none refused for its rate
    inference.status = 400
    status, error = await _refused(hosted, key)
    assert (status, error["code"], error["status"]) == (400, "E_INVALID", 400)
    assert error["message"] == "The model refused the request: This model's context is 32768 tokens."
    inference.said = "plain words"
    assert (await _refused(hosted, key))[1]["message"] == "The model refused the request: plain words"
    inference.status = 500
    assert (await _refused(hosted, key))[0] == 503
    assert (await _refused(hosted, key, ASK | {"stream": True}))[0] == 503
    inference.status, inference.raw = 200, b"<html>"
    assert (await _refused(hosted, key))[1]["reason"] == "inference"
    inference.raw, inference.down = None, True
    assert (await _refused(hosted, key))[0] == 503
    shown = await billing(hosted, who)
    assert shown["tokens"]["used"] == 0 and shown["tokens"]["models"] == []


async def test_without_an_inference_server_it_is_unavailable(
    engine: AsyncEngine, vector: None, stripe: FakeStripe, inference: FakeInference
) -> None:
    async for hosted in hosted_client(
        HOSTED.model_copy(update={"inference_url": "", "inference_key": ""}), stripe, inference
    ):
        _, key = await org_with_key(engine, hosted)
        status, error = await _refused(hosted, key)
        assert (status, error["reason"]) == (503, "inference_off")


async def test_redis_down_is_unavailable(
    engine: AsyncEngine, hosted: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, key = await org_with_key(engine, hosted)

    async def down(*_: Any) -> None:
        raise RedisError("down")

    monkeypatch.setattr(meter, "rate", down)
    status, error = await _refused(hosted, key)
    assert (status, error["code"]) == (503, "E_UNAVAILABLE")


async def test_the_plans_calls_a_second_hold() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    org = uuid.uuid4()
    await meter.rate(redis, org, None)  # by contract: no limit
    await meter.rate(redis, org, 1)
    with pytest.raises(RateLimited) as refused:
        await meter.rate(redis, org, 1)
    assert refused.value.detail["max"] == 1 and "1 calls a second" in refused.value.message
    await redis.aclose()


class _Cut:
    """A stream that the caller leaves after its first line."""

    closed = False

    async def aiter_lines(self) -> Any:
        yield 'data: {"choices": [{"delta": {"content": "Hello there"}}]}'
        yield "data: [DONE]"

    async def aclose(self) -> None:
        self.closed = True


async def test_a_stream_cut_off_is_charged_from_an_estimate(engine: AsyncEngine, hosted: httpx.AsyncClient) -> None:
    who = await person(engine)
    state = type("State", (), {"engine": engine})()
    model, cut = registry.find(MODEL), _Cut()
    assert model is not None
    relay = proxy.relay(state, Admitted(who.org_id, "Free", 250_000), model, ASK, cut)  # type: ignore[arg-type]
    assert await anext(relay) == b'data: {"choices": [{"delta": {"content": "Hello there"}}]}\n'
    await relay.aclose()
    assert cut.closed
    days = (await hosted.get(f"{API}/v1/llm/usage", headers=who.headers)).json()["days"]
    assert (days[0]["output_tokens"], days[0]["requests"]) == (3, 1)  # 11 characters / 4


def test_the_registry_is_checked_when_read() -> None:
    good = {
        "id": "adal-7b-2-0-beta", "name": "x", "status": "beta", "context_tokens": 1, "input_cents_per_mtok": 1,
        "output_cents_per_mtok": 1, "allowance_weight": 0.5, "released": "2026-11-10", "summary": "",
    }  # fmt: skip
    assert registry.parse({"models": [good]})["adal-7b-2-0-beta"].weighed(3, 0) == 2
    for bad in ({"id": "ada-1-0"}, {"status": "retired"}, {"input_cents_per_mtok": -1}, {"allowance_weight": 0}):
        with pytest.raises(RuntimeError, match=r"models\.json"):
            registry.parse({"models": [good | bad]})
    with pytest.raises(RuntimeError, match="twice"):
        registry.parse({"models": [good, good]})
    assert registry.find(None) is None and registry.find("nothing") is None
    model = registry.find(MODEL)
    assert model is not None and model.cost_micros(10**6, 10**6) == 3_000_000 and model.cost_micros(5, 5, 0) == 0
    assert meter.split(0, 0, 10) == 0.0 and meter.split(10, 5, 10) == 0.5 and meter.split(10, 0, None) == 0.0
