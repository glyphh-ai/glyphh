"""The screener card (mcp/panel.py, `ui://glyphh/screener/1`; mcp/tools/screener.py): screener_verdict names it,
it is listed and read while Ada Cloud is on, the tool answers the verdict it was given for the card to draw, and a
signal's `teach` records the person's answer exactly as the card does: the named tool, its args and the outcome.
The calls are the ones the Resume Screener plugin's skill makes, in its order: the models made, the nearest
applications asked for, each model asked to decide, the verdict shown, the answer recorded."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from glyphh_server.mcp import panel
from tests.ada.mcp import data, refused, rpc, signed_in, text, tool
from tests.db.helpers import person

CARD = "ui://glyphh/screener/1"
TIMING: dict[str, Any] = {
    "name": "screener-timing",
    "layers": [{"name": "t", "segments": [{"name": "s", "roles": [
        {"name": "flags"},
        {"name": "hops", "numeric_config": {"min_value": 0, "max_value": 20, "bin_width": 1}},
        {"name": "id", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"ask_below": 0.7},
}  # fmt: skip
OTHERS: dict[str, Any] = {
    "name": "screener-others",
    "layers": [
        {"name": "history", "segments": [{"name": "s", "roles": [
            {"name": "employers"}, {"name": "history_who", "similarity_weight": 0}]}]},
        {"name": "who", "similarity_weight": 0, "segments": [{"name": "s", "roles": [
            {"name": "id", "key_part": True, "similarity_weight": 0}]}]},
    ],
}  # fmt: skip


def held(mid: str, employers: list[str]) -> dict[str, Any]:
    return {"history": {"s": {"employers": employers, "history_who": mid}}, "who": {"s": {"id": mid}}}


async def test_the_skills_calls_end_in_the_card_and_the_persons_answer_is_recorded(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    tools = {t["name"]: t for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert tools["screener_verdict"]["_meta"] == {"ui": {"resourceUri": CARD}}
    assert tools["screener_verdict"]["annotations"]["readOnlyHint"] is True
    assert panel.SCREENER_RESOURCE in (await rpc(ada, auth, "resources/list"))["result"]["resources"]
    answered = (await rpc(ada, auth, "resources/read", uri=CARD))["result"]
    assert (answered["ttlMs"], answered["cacheScope"]) == (0, "private")
    (read,) = answered["contents"]
    assert read["mimeType"] == "text/html;profile=mcp-app" and "window.McpApp=" in read["text"]
    assert (
        "__APP_JS__" not in read["text"]
        and "callServerTool" in read["text"]
        and "Is this a real person?" in read["text"]
    )

    await tool(ada, auth, "ada_model_create", name="screener-timing", spec=TIMING)
    await tool(ada, auth, "ada_model_create", name="screener-others", spec=OTHERS)
    await tool(ada, auth, "ada_record", name="screener-others", data=held("a1", ["acme", "bolt"]), outcome="alone")
    near = data(await tool(ada, auth, "ada_facts", name="screener-others", top=8,
                           data={"history": {"s": {"employers": ["acme", "bolt"]}}}))  # fmt: skip
    assert len(near["facts"]) == 1 and near["facts"][0]["score"] > 0.9
    case = {"t": {"s": {"flags": ["future_date"], "hops": 2, "id": "m1"}}}
    decided = data(await tool(ada, auth, "ada_decide", name="screener-timing", data=case))
    assert decided["ask"] is True  # nothing is held: Ada is unsure, so the person is asked

    teach = {"tool": "ada_record", "args": {"name": "screener-timing", "data": case}}
    verdict = {
        "applicant": "Ann Lee - data analyst", "role": "data analyst", "id": "m1", "keep": {"left": "out"},
        "person": {"verdict": "unsure", "ask": ["timing"], "signals": [
            {"signal": "timing", "title": "Email timestamps", "says": "unsure", "by": "rule", "teach": teach,
             "found": ["the email is dated after a server already had it, or after now"]},
            {"signal": "others", "title": "Against the other applications", "says": "fine", "by": "ada",
             "found": ["nothing like it is held"], "near": {}},
        ]},
        "fit": {"outcome": "strong", "confidence": 0.88, "ask": False, "found": ["2 jobs over 8 years"]},
        "made": {"outcome": "no answer", "confidence": None, "ask": True, "found": []},
    }  # fmt: skip
    shown = await tool(ada, auth, "screener_verdict", **verdict)
    assert text(shown) == ("Ann Lee - data analyst: unsure (Email timestamps: unsure; Against the other applications: "
                           "fine). Strong fit.")  # fmt: skip
    card = data(shown)
    assert card["person"]["signals"][0]["teach"] == teach and card["person"]["verdict"] == "unsure"
    assert "keep" not in card and "id" not in card and "confidence" not in card["made"]
    assert card["fit"] == verdict["fit"] and "near" not in card["person"]["signals"][1]
    kept = data(await tool(ada, auth, teach["tool"], **teach["args"], outcome="suspect"))
    assert kept["precedents"] == 1

    unsure = verdict | {"fit": {"outcome": "poor", "ask": True}}
    assert text(await tool(ada, auth, "screener_verdict", **unsure)).endswith("Fit unsure (poor).")
    wrong = verdict | {"person": {"verdict": "fake", "signals": []}}
    assert (await refused(ada, auth, "screener_verdict", **wrong))["code"] == "E_INVALID"
