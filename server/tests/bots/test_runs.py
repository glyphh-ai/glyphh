"""A bot's runs, end to end with Claude and Pipedream faked: the tools it is offered (only its scope's), a tool call
run as the org with the connection's account, every step kept, its tokens metered, and each way a run stops."""

from types import SimpleNamespace

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotRun, LlmUsageDay
from glyphh_server.ops.bots import runs
from tests.bots.conftest import BOTS, Served, connected, made_bot, serve
from tests.bots.fakes import FakePipedream, reply, text, use
from tests.db.helpers import Person, person

SEND_ARGS = {"to": ["grace@navy.test"], "subject": "Hi", "body": "Hello"}


async def scoped(s: Served, who: Person, **over: object) -> dict:
    bot = await made_bot(s, who, **over)
    gmail = await connected(s, who)
    scopes = {"connections": [{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}]}
    res = await s.http.put(f"/v1/bots/{bot['slug']}/connections", json=scopes, headers=who.headers)
    assert res.status_code == 200, res.text
    return bot


async def ran(s: Served, who: Person, slug: str = "inbox-cat", given: str = "Mail Grace") -> dict:
    res = await s.http.post(f"/v1/bots/{slug}/runs", json={"input": given}, headers=who.headers)
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"
    await s.settled()
    return dict((await s.http.get(f"/v1/bot-runs/{res.json()['id']}", headers=who.headers)).json())


async def test_a_run_uses_its_scoped_tool_as_the_org_and_keeps_every_step(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await scoped(served, ada)
    served.claude.replies = [
        reply(text("Sending it."), use("gmail-send-email", SEND_ARGS), stop="tool_use"),
        reply(text("Sent to Grace."), tokens=(1500, 100)),
    ]
    run = await ran(served, ada)
    assert run["status"] == "done" and run["output"] == "Sent to Grace." and run["error"] == ""
    assert [(s["kind"], s["name"], s["is_error"]) for s in run["steps"]] == [
        ("text", "claude", False),
        ("tool", "gmail-send-email", False),
        ("text", "claude", False),
    ]
    assert run["steps"][1]["output"] == {"exports": {"$summary": "Sent"}, "ret": {"id": "msg_1"}}
    assert (run["input_tokens"], run["output_tokens"], run["cost_micros"]) == (2500, 300, 0)  # within the plan
    assert served.pd.runs == [
        {
            "id": "gmail-send-email",
            "external_user_id": f"org_{ada.org_id}",
            "configured_props": {**SEND_ARGS, "gmail": {"authProvisionId": "apn_1"}},
        }
    ]
    first = served.claude.requests[0]
    assert [t["name"] for t in first["tools"]] == ["gmail-send-email"]  # only its scope's, no Ada (Ada Cloud off)
    schema = first["tools"][0]["input_schema"]
    assert set(schema["properties"]) == {"to", "subject", "body", "format"} and schema["required"] == ["to", "subject"]
    assert schema["properties"]["format"]["enum"] == ["text", "html"]
    assert (first["model"], first["betas"], first["fallbacks"]) == (
        "claude-opus-5-5",
        ["server-side-fallback-2026-07-01"],
        "default",
    )
    assert first["output_config"] == {"effort": "high"} and "tool_choice" not in first
    assert first["messages"] == [{"role": "user", "content": "Mail Grace"}]
    answered = served.claude.requests[1]["messages"][2]["content"][0]
    assert answered["tool_use_id"] == "tu_1" and answered["is_error"] is False
    async with engine.begin() as conn:
        day = (await conn.execute(select(LlmUsageDay).where(LlmUsageDay.org_id == ada.org_id))).one()
    assert (day.model, day.input_tokens, day.output_tokens, day.requests) == ("claude-opus-5-5", 2500, 300, 2)
    bot = (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()
    assert bot["last_run"]["id"] == run["id"] and bot["last_run"]["status"] == "done"
    listed = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ada.headers)).json()["runs"]
    assert [r["id"] for r in listed] == [run["id"]]


async def test_a_failing_tool_and_one_out_of_scope_are_errors_claude_sees(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await scoped(served, ada)
    served.pd.fail_run = True
    served.claude.replies = [
        reply(use("gmail-send-email", SEND_ARGS, "tu_1"), use("gmail-find-email", {"q": "x"}, "tu_2"), stop="tool_use"),
        reply(text("Could not send.")),
    ]
    run = await ran(served, ada)
    assert run["status"] == "done"
    assert [(s["name"], s["is_error"]) for s in run["steps"][:2]] == [
        ("gmail-send-email", True),
        ("gmail-find-email", True),
    ]
    results = served.claude.requests[1]["messages"][2]["content"]
    assert [(r["tool_use_id"], r["is_error"]) for r in results] == [("tu_1", True), ("tu_2", True)]
    assert "revoked" in results[0]["content"] and "may not use" in results[1]["content"]


async def test_a_run_stops_at_its_turns(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await scoped(served, ada, limits={"max_turns": 2, "usd_per_run": 2.0})
    served.claude.replies = [reply(use("gmail-send-email", SEND_ARGS), stop="tool_use")]
    run = await ran(served, ada)
    assert run["status"] == "failed" and "limit of 2 turns" in run["error"] and len(served.claude.requests) == 2


async def test_a_run_stops_at_its_dollars(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await scoped(served, ada, limits={"max_turns": 20, "usd_per_run": 0.01})
    # 1,000 in and 1,000 out on Opus: 0.4 + 2 cents, past the run's cent after the first turn
    served.claude.replies = [reply(use("gmail-send-email", SEND_ARGS), stop="tool_use", tokens=(1000, 1000))]
    run = await ran(served, ada)
    assert run["status"] == "failed" and "spent its limit, $0.01" in run["error"] and len(served.claude.requests) == 1


async def test_a_refusal_and_a_cut_off_turn_fail_the_run_and_pause_turn_goes_on(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await made_bot(served, ada, model="claude-haiku-5-5")
    refused = reply(stop="refusal")
    refused.stop_details = SimpleNamespace(category="cyber")
    served.claude.replies = [refused]
    run = await ran(served, ada)
    assert run["status"] == "failed" and "declined the job (cyber)" in run["error"]
    assert "fallbacks" not in served.claude.requests[0] and "tools" not in served.claude.requests[0]
    served.claude.replies = [reply(text("Half"), stop="max_tokens")]
    assert "past its room" in (await ran(served, ada))["error"]
    served.claude.replies = [reply(stop="pause_turn"), reply(text("Finished."))]
    run = await ran(served, ada)
    assert run["status"] == "done" and run["output"] == "Finished."


async def test_without_an_anthropic_key_a_run_is_refused(engine: AsyncEngine) -> None:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": ""}), FakePipedream()):
        s.app.state.bots.claude = None
        ada = await person(engine)
        await made_bot(s, ada)
        res = await s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "anthropic_off"


async def test_a_restart_fails_this_machines_runs_it_cut_off(engine: AsyncEngine) -> None:
    pd = FakePipedream()
    async for s in serve(BOTS, pd):
        ada = await person(engine)
        bot = await made_bot(s, ada)
    async with engine.begin() as conn:
        values = {"org_id": ada.org_id, "bot_id": bot["id"], "status": "running", "machine": runs.machine()}
        cut = (await conn.execute(insert(BotRun).values(values).returning(BotRun.id))).scalar_one()
        elsewhere = values | {"machine": "another-machine"}
        kept = (await conn.execute(insert(BotRun).values(elsewhere).returning(BotRun.id))).scalar_one()
    async for s in serve(BOTS, pd):
        first = (await s.http.get(f"/v1/bot-runs/{cut}", headers=ada.headers)).json()
        assert (first["status"], first["error"]) == ("failed", runs.INTERRUPTED)
        assert (await s.http.get(f"/v1/bot-runs/{kept}", headers=ada.headers)).json()["status"] == "running"
