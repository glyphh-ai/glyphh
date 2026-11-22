"""Training a bot end to end through the connector, as Claude does: find its decisions, read one with its nearest
precedents, relabel one and many, confirm, add a case, forget a precedent, read the gates' stats and backtest them;
each tool listed with its read-only and destructive hints."""

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import Served
from tests.bots.test_decisions import GATE, asked_once
from tests.connector import granted, rpc, tool

TRAINING = {
    "bot_decisions": (True, None), "bot_decision": (True, None), "bot_relabel": (False, True),
    "bot_relabel_many": (False, True), "bot_confirm": (False, False), "bot_add_case": (False, False),
    "bot_forget_case": (False, True), "bot_gate_stats": (True, None), "bot_backtest": (True, None),
}  # fmt: skip


async def test_claude_trains_a_bot_through_the_connector(served: Served, engine: AsyncEngine) -> None:
    ada, _ = await asked_once(served, engine)
    _, auth = await granted(engine, ada)
    listed = {t["name"]: t["annotations"] for t in (await rpc(served.http, auth, "tools/list"))["result"]["tools"]}
    for name, (read_only, destructive) in TRAINING.items():
        assert listed[name]["readOnlyHint"] is read_only and listed[name].get("destructiveHint") is destructive

    found = await tool(served.http, auth, "bot_decisions", slug="inbox-cat", limit=1)
    text = found["content"][0]["text"]
    assert text.startswith("2 decisions; next page: cursor ") and "by you" in text
    rest = await tool(served.http, auth, "bot_decisions", slug="inbox-cat", q="won")
    won = rest["structuredContent"]["decisions"][0]
    assert rest["content"][0]["text"].splitlines()[1].startswith("[skip] You won! (gate worth, by you;")
    served.ada.rule[GATE] = lambda case: ("answer", 0.9)
    one = (await tool(served.http, auth, "bot_decision", decision_id=won["id"]))["content"][0]["text"]
    assert "subject: You won!" in one and "p1: answer, 100% alike" in one and "Outcomes: answer, skip" in one

    fixed = await tool(served.http, auth, "bot_relabel", decision_id=won["id"], outcome="answer")
    assert "corrected to answer" in fixed["content"][0]["text"]
    ids = [d["id"] for d in found["structuredContent"]["decisions"]] + [won["id"]]
    many = await tool(served.http, auth, "bot_relabel_many", slug="inbox-cat", ids=ids, outcome="skip")
    assert many["isError"] is False and "relabelled skip" in many["content"][0]["text"]
    sure = await tool(served.http, auth, "bot_confirm", slug="inbox-cat", ids=[won["id"]])
    assert "confirmed right" in sure["content"][0]["text"]
    item = {"id": "m7", "subject": "Invoice due"}
    added = await tool(served.http, auth, "bot_add_case", slug="inbox-cat", gate="worth", outcome="answer", item=item)
    assert "[answer] Invoice due (gate worth, by you" in added["content"][0]["text"]
    gone = await tool(served.http, auth, "bot_forget_case", slug="inbox-cat", gate="worth", precedent_id="p1")
    assert gone["content"][0]["text"].startswith("Gate worth forgot p1; it holds ")
    stats = await tool(served.http, auth, "bot_gate_stats", slug="inbox-cat")
    assert stats["content"][0]["text"].startswith("worth: 2 decisions (Ada 0, you 2, default 0); asks 100%")
    served.ada.rule[GATE] = lambda case: ("answer", 0.5)
    tested = await tool(served.http, auth, "bot_backtest", slug="inbox-cat", gate="worth")
    said = tested["content"][0]["text"]
    assert said.startswith("Replayed 3: 0 the same, 3 would change or ask") and "(asks)" in said
    del served.ada.specs[GATE]  # a bot whose gate model is gone: nothing to stand on
    none = await tool(served.http, auth, "bot_decision", decision_id=won["id"])
    assert "Nearest precedents:\n  none" in none["content"][0]["text"]
    served.ada.specs[GATE] = {}
    empty = await tool(served.http, auth, "bot_gate_stats", slug="inbox-cat", gate="worth", days=1)
    assert empty["isError"] is False
