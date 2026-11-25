"""The closeness card (mcp/panel.py, `ui://glyphh/closeness/1`; mcp/tools/closeness.py): screener_closeness names
it, it is listed and read while Ada Cloud is on, and the tool answers what the Resume Screener plugin's check
worked out, Ada's fact tree included exactly as Ada gave it. The calls before it are the plugin's own: a model
holding fakes and real ones, the nearest on each side (ada_facts), Ada's decision with its facts (ada_decide)."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from glyphh_server.mcp import panel
from tests.ada.mcp import data, refused, rpc, signed_in, text, tool
from tests.db.helpers import person

CARD = "ui://glyphh/closeness/1"
SPEC: dict[str, Any] = {
    "name": "screener-closeness",
    "layers": [
        {"name": "resume", "similarity_weight": 0.3, "segments": [{"name": "s", "roles": [
            {"name": "duties", "text_encoding": "bag_of_words"}, {"name": "resume_who", "similarity_weight": 0}]}]},
        {"name": "side", "similarity_weight": 1.0, "segments": [{"name": "s", "roles": [{"name": "is"}]}]},
        {"name": "who", "similarity_weight": 0, "segments": [{"name": "s", "roles": [
            {"name": "id", "key_part": True, "similarity_weight": 0}]}]},
    ],
    "settings": {"lexicon": False},
}  # fmt: skip


def held(mid: str, side: str, duties: str) -> dict[str, Any]:
    case = {
        "resume": {"s": {"duties": duties, "resume_who": mid}},
        "side": {"s": {"is": side}},
        "who": {"s": {"id": mid}},
    }
    return {"data": case, "outcome": side}


async def test_the_plugins_check_ends_in_the_card_with_adas_fact_tree_as_ada_gave_it(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    tools = {t["name"]: t for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert tools["screener_closeness"]["_meta"] == {"ui": {"resourceUri": CARD}}
    assert tools["screener_closeness"]["annotations"]["readOnlyHint"] is True
    assert panel.CLOSENESS_RESOURCE in (await rpc(ada, auth, "resources/list"))["result"]["resources"]
    (read,) = (await rpc(ada, auth, "resources/read", uri=CARD))["result"]["contents"]
    assert read["mimeType"] == "text/html;profile=mcp-app" and "window.McpApp=" in read["text"]
    assert "__APP_JS__" not in read["text"] and "Closest fake" in read["text"] and "Fact tree" in read["text"]

    await tool(ada, auth, "ada_model_create", name="screener-closeness", spec=SPEC)
    cases = [held(f"f{i}", "fake", f"leveraged synergy to drive results {i}") for i in range(6)]
    cases += [held(f"r{i}", "real", f"stocked shelves and ran the till {i}") for i in range(6)]
    await tool(ada, auth, "ada_record_many", name="screener-closeness", cases=cases)
    mine = {"resume": {"s": {"duties": "leveraged synergy to drive results daily"}}}
    near = data(await tool(ada, auth, "ada_facts", name="screener-closeness", top=4,
                           data=mine | {"side": {"s": {"is": "real"}}}))  # fmt: skip
    assert {f["outcome"] for f in near["facts"]} == {"real"}  # naming the side puts that side first
    layers = {c["key"]: c for c in near["facts"][0]["tree"]["children"]}
    assert layers["resume"]["score"] < 0.5 < layers["side"]["score"]  # how alike is the resume's own score
    decided = data(await tool(ada, auth, "ada_decide", name="screener-closeness", data=mine, include=["facts"]))
    assert decided["outcome"] == "fake" and decided["facts"][0]["tree"]["children"][0]["key"] == "resume"

    check = {
        "resume": {
            "fake": {"closeness": 0.91, "nearest": [{"closeness": 0.91, "like": "Keisha Dubois - backend engineer"}]},
            "real": {"closeness": 0.2, "nearest": [{"closeness": 0.2, "like": "your own applicants"}]},
            "reads": "reads like the fakes",
        },
        "letter": {"fake": {"closeness": 0.3, "nearest": []}, "real": {"closeness": None, "nearest": []},
                   "reads": "only fakes are held to compare it with"},
        "decision": {"outcome": "fake", "confidence": 0.87, "ask": True, "on": "resume",
                     "probabilities": {"fake": 0.87}, "facts": decided["facts"]},
        "could not read": [],
    }  # fmt: skip
    shown = await tool(ada, auth, "screener_closeness", **check)
    assert text(shown) == (
        "The resume: closest fake 0.91, closest real 0.20: reads like the fakes. The cover letter: closest fake 0.30, "
        "closest real none held: only fakes are held to compare it with. Ada decides fake (87%); Ada would ask a "
        "person first."
    )
    card = data(shown)
    assert card["decision"]["facts"] == decided["facts"] and card["resume"] == check["resume"]
    assert "could not read" not in card and "probabilities" not in card["decision"]
    assert "closeness" not in card["letter"]["real"]

    bare = await tool(ada, auth, "screener_closeness", reads="there was nothing to read")
    assert text(bare) == "there was nothing to read" and data(bare) == {"reads": "there was nothing to read"}
    assert text(await tool(ada, auth, "screener_closeness")) == "There was nothing to read."
    unsure = {"decision": {"outcome": "real"}}
    assert text(await tool(ada, auth, "screener_closeness", **unsure)) == "Ada decides real."
    wrong = {"resume": {"fake": {"closeness": 7}, "real": {}, "reads": "x"}}
    assert (await refused(ada, auth, "screener_closeness", **wrong))["code"] == "E_INVALID"
