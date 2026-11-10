"""POST /v1/chat/completions at the Ada host: proxied to the inference server, drawn from the plan's month of tokens,
charged to the overage balance past it (split at its edge), refused 402 E_BALANCE with neither left."""

import json
import math

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes import FakeInference
from tests.llm.conftest import API, ASK, MODEL, billing, holding, org_with_key


async def test_the_models_and_their_rates_are_listed_on_both_hosts(hosted: httpx.AsyncClient) -> None:
    here, there = (await hosted.get("/v1/llm/models")).json(), (await hosted.get(f"{API}/v1/llm/models")).json()
    assert (
        here
        == there
        == {
            "models": [
                {
                    "id": MODEL,
                    "name": "adaL 34B 1.0",
                    "status": "stable",
                    "context_tokens": 32_768,
                    "input_cents_per_mtok": 60,
                    "output_cents_per_mtok": 240,
                    "allowance_weight": 1.0,
                    "released": "2026-11-10",
                    "summary": "Glyphh's hosted 34B model.",
                }
            ]
        }
    )


async def test_a_request_within_the_month_is_answered_and_counted_not_charged(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted)
    res = await hosted.post("/v1/chat/completions", json=ASK | {"temperature": 0.2}, headers=key)
    assert res.status_code == 200, res.text
    assert res.json()["choices"][0]["message"]["content"] == "Hello!"
    assert res.json()["usage"] == {"prompt_tokens": 1_000, "completion_tokens": 500}
    assert inference.calls == [("Bearer ik_test", ASK | {"temperature": 0.2})]
    shown = await billing(hosted, who)
    assert shown["tokens"]["used"] == 1_500 and shown["tokens"]["max"] == 250_000 and shown["tokens"]["over_used"] == 0
    model = {"id": MODEL, "name": "adaL 34B 1.0", "input_tokens": 1_000, "output_tokens": 500, "requests": 1}
    assert shown["tokens"]["models"] == [model | {"charged_cents": 0.0, "charged_micros": 0}]
    assert shown["balance"] == {"cents": 0.0, "micros": 0, "low": True}
    signed_in = await hosted.post("/v1/chat/completions", json=ASK, headers=who.headers)  # a sign-in, as the Ada API
    assert signed_in.status_code == 200
    assert (await hosted.post("/v1/chat/completions", json=ASK)).status_code == 401


async def test_past_the_month_the_balance_is_charged_split_at_the_edge(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted)
    await holding(engine, who.org_id, micros=10_000_000, tokens=249_000)  # $10, 1,000 tokens of the month left
    inference.usage = {"prompt_tokens": 1_000, "completion_tokens": 1_000}
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200
    half = math.ceil((1_000 * 60 + 1_000 * 240) * 0.5 / 100)  # half its tokens past the month: 1,500 micros
    assert half == 1_500
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200  # wholly past
    shown = await billing(hosted, who)
    assert (shown["tokens"]["used"], shown["tokens"]["over_used"]) == (250_000, 3_000)
    assert shown["tokens"]["models"][0]["charged_micros"] == 4_500 and shown["tokens"]["models"][0]["requests"] == 2
    assert shown["balance"] == {"cents": 999.55, "micros": 9_995_500, "low": False}
    entries = (await hosted.get(f"{API}/v1/billing/ledger", headers=who.headers)).json()["entries"]
    assert [(e["kind"], e["amount_micros"], e["amount_cents"], e["model"]) for e in entries] == [
        ("charge", -4_500, -0.45, MODEL)  # one entry a model a day, each request's charge added to it
    ]
    days = (await hosted.get(f"{API}/v1/llm/usage", headers=who.headers)).json()["days"]
    assert [(d["model"], d["input_tokens"], d["output_tokens"], d["requests"], d["charged_micros"]) for d in days] == [
        (MODEL, 2_000, 2_000, 2, 4_500)
    ]
    assert days[0]["day"] == entries[0]["note"] and days[0]["charged_cents"] == 0.45


async def test_with_no_month_and_no_balance_left_a_request_is_refused_402(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted)
    await holding(engine, who.org_id, micros=1, tokens=250_000)  # a microdollar: let in, then below 0
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200
    refused = await hosted.post("/v1/chat/completions", json=ASK, headers=key)
    error = refused.json()["error"]
    assert (refused.status_code, error["code"], error["reason"]) == (402, "E_BALANCE", "tokens")
    assert (error["used"], error["max"], error["balance_cents"]) == (251_500, 250_000, -0.1799)
    assert error["topup"] == "http://localhost:3000/settings/billing"
    assert "250,000 tokens this month are used" in error["message"] and "$-0.00" in error["message"]
    assert len(inference.calls) == 1  # never sent on
    await holding(engine, who.org_id, micros=0, tokens=999_999, period="2026-01")  # an old month's: the month turned
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200


async def test_by_contract_nothing_is_charged_or_refused(engine: AsyncEngine, hosted: httpx.AsyncClient) -> None:
    who, key = await org_with_key(engine, hosted, "Enterprise")
    await holding(engine, who.org_id, tokens=10**12)
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200
    shown = await billing(hosted, who)
    assert (shown["tokens"]["max"], shown["tokens"]["over_used"], shown["balance"]["micros"]) == (None, 0, 0)


async def test_a_stream_is_passed_on_and_charged_from_its_last_chunk(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted)
    await holding(engine, who.org_id, micros=10_000_000, tokens=250_000)
    asked = ASK | {"stream": True, "stream_options": {"continuous_usage_stats": False}}
    res = await hosted.post("/v1/chat/completions", json=asked, headers=key)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    assert '"usage": {"prompt_tokens": 1000' in res.text and res.text.endswith("data: [DONE]\n\n")
    sent = inference.calls[0][1]
    assert sent["stream_options"] == {"continuous_usage_stats": False, "include_usage": True}  # forced on
    charged = math.ceil((1_000 * 60 + 500 * 240) / 100)
    assert (await billing(hosted, who))["balance"]["micros"] == 10_000_000 - charged


async def test_an_answer_that_gives_no_usage_is_charged_from_an_estimate(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    who, key = await org_with_key(engine, hosted)
    inference.usage = None
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 200
    streamed = await hosted.post("/v1/chat/completions", json=ASK | {"stream": True}, headers=key)
    assert streamed.status_code == 200
    one_in = math.ceil(len(json.dumps(ASK["messages"])) / 4)
    days = (await hosted.get(f"{API}/v1/llm/usage?days=1", headers=who.headers)).json()["days"]
    out = math.ceil(len("Hello!") / 4) + math.ceil(len("Hello!") / 4)  # "Hello!" whole, and "Hel" "lo" "!" streamed
    assert (days[0]["input_tokens"], days[0]["output_tokens"], days[0]["requests"]) == (2 * one_in, out, 2)


async def test_a_bad_request_is_refused_before_the_model(
    engine: AsyncEngine, hosted: httpx.AsyncClient, inference: FakeInference
) -> None:
    _, key = await org_with_key(engine, hosted)
    chat = "/v1/chat/completions"
    missing = await hosted.post(chat, json=ASK | {"model": "gpt-4"}, headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    assert "GET /v1/llm/models" in missing.json()["error"]["message"]
    for bad in (b"not json", b"[]", json.dumps({"model": MODEL}).encode()):
        res = await hosted.post(chat, content=bad, headers=key | {"content-type": "application/json"})
        assert (res.status_code, res.json()["error"]["code"]) == (400, "E_INVALID")
    big = await hosted.post(chat, content=b" " * ((1 << 20) + 1), headers=key)
    assert (big.status_code, big.json()["error"]["code"]) == (413, "E_TOO_LARGE")
    assert inference.calls == []
