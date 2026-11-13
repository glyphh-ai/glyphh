"""The decision card (mcp/panel.py, `ui://glyphh/decision/1`): ada_decide and a template's decide tool name it, it is
listed and read while Ada Cloud is on, and an answer's `teach` records the case exactly as the card does on Approve
or a correction: the named tool, its args, the case's data and the person's outcome."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from glyphh_server.mcp import panel
from tests.ada.conftest import SHAPES, cases, shape
from tests.ada.mcp import data, rpc, signed_in, tool
from tests.ada.test_outputs import MULTI
from tests.db.helpers import person

CARD = "ui://glyphh/decision/1"


async def test_ada_decide_shows_the_card_and_its_answer_teaches_ada_record(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    tools = {t["name"]: t for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert tools["ada_decide"]["_meta"] == {"ui": {"resourceUri": CARD}}
    assert "_meta" not in tools["ada_record"] and "_meta" not in tools["ada_query"]
    listed = (await rpc(ada, auth, "resources/list"))["result"]["resources"]
    assert panel.DECISION_RESOURCE in listed
    (read,) = (await rpc(ada, auth, "resources/read", uri=CARD))["result"]["contents"]
    assert read["mimeType"] == "text/html;profile=mcp-app" and "window.McpApp=" in read["text"]
    assert "__APP_JS__" not in read["text"] and "callServerTool" in read["text"] and "ontoolinput" in read["text"]

    await tool(ada, auth, "ada_model_create", name="shapes", spec=SHAPES)
    await tool(ada, auth, "ada_record_many", name="shapes", cases=cases(40))
    case = shape(900, "r", 2)
    answer = data(await tool(ada, auth, "ada_decide", name="shapes", data=case))
    assert answer["teach"] == {"tool": "ada_record", "args": {"name": "shapes"}}
    corrected = "bad" if answer["outcome"] == "good" else "good"
    kept = data(await tool(ada, auth, answer["teach"]["tool"], **answer["teach"]["args"], data=case, outcome=corrected))
    assert kept["precedents"] == 41


async def test_a_decision_of_several_outputs_teaches_each_outcome(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "ada_model_create", name="tickets", spec=MULTI)
    tickets = [
        {"data": {"t": {"w": {"product": p, "text": t, "ref": f"r{n}"}}}, "outcomes": {"team": team, "urgent": "no"}}
        for n, (p, t, team) in enumerate([("app", "refund please", "billing"), ("web", "login error", "tech")] * 6)
    ]
    await tool(ada, auth, "ada_record_many", name="tickets", cases=tickets)
    case = {"t": {"w": {"product": "app", "text": "refund please now", "ref": "r99"}}}
    answer = data(await tool(ada, auth, "ada_decide", name="tickets", data=case, outputs=["team", "urgent"]))
    assert set(answer["outputs"]) == {"team", "urgent"} and answer["teach"]["tool"] == "ada_record"
    outcomes = {"team": answer["outputs"]["team"]["outcome"], "urgent": "yes"}
    kept = data(await tool(ada, auth, "ada_record", **answer["teach"]["args"], data=case, outcomes=outcomes))
    assert kept["precedents"] == 13


async def test_a_templates_decide_shows_the_card_and_teaches_its_record_tool(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "template_install", slug="orchestrator")
    tools = {t["name"]: t for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert tools["glyphh_bot_decide"]["_meta"] == {"ui": {"resourceUri": CARD}}
    assert "_meta" not in tools["glyphh_bot_record"] and "_meta" not in tools["glyphh_orchestrator_recall"]
    job = {"case": {"bot": {"job": "triage the inbox", "recurs_per_week": 20, "touches": "drafts", "similar_bots": 0}}}
    answer = data(await tool(ada, auth, "glyphh_bot_decide", model="make_bot", data=job))
    full = f"me-{who.user_id.hex[:12]}-orchestrator-make_bot"
    assert answer["teach"] == {"tool": "glyphh_bot_record", "args": {"model": full}}
    kept = data(await tool(ada, auth, answer["teach"]["tool"], **answer["teach"]["args"], data=job, outcome="make"))
    assert kept["model"] == full and kept["precedents"] == 1
