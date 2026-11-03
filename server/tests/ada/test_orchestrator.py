"""The Orchestrator template (docs/specs/templates.md, section 3) as Claude uses it: installed with each model from
its own spec, its gates asked and taught, a bot's own gates made, asked and taught, its memory of bots, the hooks'
context, and the template removed with every model it made."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.mcp import data, rpc, signed_in, text, tool
from tests.db.helpers import person

API = "http://api.test"
MINE = {
    "glyphh_orchestrator_remember",
    "glyphh_orchestrator_recall",
    "glyphh_orchestrator_forget",
    "glyphh_bot_model",
    "glyphh_bot_decide",
    "glyphh_bot_record",
}
GATE: dict[str, Any] = {
    "seed": 3,
    "dimension": 2048,
    "layers": [
        {"name": "run", "segments": [{"name": "s", "roles": [{"name": "news", "text_encoding": "bag_of_words"}]}]}
    ],
    "output": {"costs": {"send": {"skip": 3}}, "ask_below": 0.6},
}


def job(text_: str, per_week: int, touches: str, similar: int = 0) -> dict[str, Any]:
    return {"case": {"bot": {"job": text_, "recurs_per_week": per_week, "touches": touches, "similar_bots": similar}}}


async def models(ada: httpx.AsyncClient, auth: dict[str, str]) -> set[str]:
    return {m["name"] for m in data(await tool(ada, auth, "ada_models"))["models"]}


async def test_the_orchestrator_learns_when_a_job_becomes_a_bot(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    made = data(await tool(ada, auth, "template_install", slug="orchestrator"))
    assert [m["key"] for m in made["models"]][3:] == ["make_bot", "trust_bot", "keep_bot"]
    assert "spec" not in made["models"][3]
    prefix = f"me-{who.user_id.hex[:12]}-orchestrator-"
    assert await models(ada, auth) == {prefix + m["key"] for m in made["models"]}
    tools = {t["name"]: t for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert set(tools) >= MINE and tools["glyphh_bot_decide"]["annotations"]["readOnlyHint"] is True
    assert tools["glyphh_bot_record"]["annotations"]["readOnlyHint"] is False
    assert tools["glyphh_bot_decide"]["description"].endswith(
        "Models: make_bot, trust_bot, keep_bot, and the ones it made. From your Orchestrator template."
    )
    assert tools["glyphh_bot_model"]["description"].endswith("At most 60 per person. From your Orchestrator template.")
    said = (await rpc(ada, auth, "server/discover"))["result"]["instructions"]
    assert "never from your own guesses" in said
    for i in range(4):
        await tool(
            ada,
            auth,
            "glyphh_bot_record",
            model="make_bot",
            data=job(f"triage inbox {i}", 20, "drafts"),
            outcome="make",
        )
        await tool(
            ada, auth, "glyphh_bot_record", model="make_bot", data=job(f"wire money {i}", 1, "pays"), outcome="no"
        )
    kept = data(await tool(ada, auth, "glyphh_bot_record", model="make_bot", data=job("x", 1, "pays"), outcome="no"))
    assert kept["model"] == prefix + "make_bot" and kept["precedents"] == 9
    asked = await tool(ada, auth, "glyphh_bot_decide", model="make_bot", data=job("triage the inbox", 20, "drafts"))
    answer = data(asked)
    assert answer["outcome"] == "make" and answer["receipts"] and set(answer["probabilities"]) == {"make", "no"}
    assert text(asked).startswith(f"{prefix}make_bot: make (")
    whole = data(
        await tool(ada, auth, "glyphh_bot_decide", model=prefix + "make_bot", data=job("wire money", 1, "pays"))
    )
    assert whole["outcome"] == "no"


async def test_a_bots_gates_are_made_asked_taught_and_removed_with_it(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "template_install", slug="orchestrator")
    made = await tool(ada, auth, "glyphh_bot_model", name="launch-watch-worth", spec=GATE)
    gate = f"me-{who.user_id.hex[:12]}-orchestrator-launch-watch-worth"
    assert text(made) == f"Made {gate}." and data(made) == {"name": "launch-watch-worth", "model": gate, "made": True}
    again = await tool(ada, auth, "glyphh_bot_model", name="launch-watch-worth", spec=GATE)
    assert text(again) == f"Kept, as it was there already: {gate}." and data(again)["made"] is False
    news = {"run": {"s": {"news": "launch numbers doubled overnight"}}}
    recorded = await tool(ada, auth, "glyphh_bot_record", model="launch-watch-worth", data=news, outcome="send")
    assert text(recorded).startswith(f"Recorded send in {gate} (") and data(recorded)["precedents"] == 1
    await tool(ada, auth, "glyphh_bot_record", model=gate, data={"run": {"s": {"news": "nothing new"}}}, outcome="skip")
    answer = data(await tool(ada, auth, "glyphh_bot_decide", model="launch-watch-worth", data=news))
    assert answer["outcome"] == "send" and answer["model"] == gate
    assert gate in await models(ada, auth)
    await tool(ada, auth, "template_install", slug="orchestrator")  # installed again: what it made is kept
    assert data(await tool(ada, auth, "glyphh_bot_decide", model="launch-watch-worth", data=news))["outcome"] == "send"
    await tool(ada, auth, "template_remove", slug="orchestrator", confirm="orchestrator")
    assert not await models(ada, auth)


async def test_its_memory_of_bots_and_the_hooks_context(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "template_install", slug="orchestrator")
    await tool(ada, auth, "glyphh_orchestrator_remember", kind="instructions", text="No bot ever pays without my yes")
    await tool(ada, auth, "glyphh_orchestrator_remember", kind="personality", text="Ask once, then act")
    run = await tool(
        ada,
        auth,
        "glyphh_orchestrator_remember",
        kind="memory",
        text="launch-watch ran fine on Monday",
        when="launch-watch run",
    )
    found = data(await tool(ada, auth, "glyphh_orchestrator_recall", about="how did launch-watch run"))["found"]
    assert found[0]["text"] == "launch-watch ran fine on Monday"
    start = (await ada.post(f"{API}/v1/me/glyphh/context", json={}, headers=who.headers)).json()["context"]
    assert "Your rules for bots:\n- No bot ever pays" in start and "How it works with you:\n- Ask once" in start
    asked = {"prompt": "run launch-watch again"}
    now = (await ada.post(f"{API}/v1/me/glyphh/context", json=asked, headers=who.headers)).json()["context"]
    assert "What it knows of your bots:\n- launch-watch ran fine" in now and "No bot ever pays" not in now
    gone = await tool(ada, auth, "glyphh_orchestrator_forget", kind="memory", id=data(run)["id"])
    assert data(gone)["forgotten"] is True
