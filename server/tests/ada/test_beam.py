"""Beam search across models (docs/specs/ada-cloud.md, 4.2): the beam itself over fake askers, then `POST /v1/beam`
and the connector's `ada_beam` over models answered by a worker, each hop one read."""

from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.api.beam import Hop, question
from glyphh_ada.beam import Asker, beam
from glyphh_ada.process import Worker
from glyphh_server.mcp.tools.ada_beam import summary
from tests.ada.conftest import a_model, an_org, key_for
from tests.ada.mcp import data, refused, signed_in, text, tool
from tests.db.helpers import person

NEXT: dict[str, Any] = {
    "name": "next",
    "seed": 5,
    "dimension": 2048,
    "layers": [
        {
            "name": "b",
            "segments": [
                {"name": "s", "roles": [{"name": "verdict"}, {"name": "id", "key_part": True, "similarity_weight": 0}]}
            ],
        }
    ],
    "output": {"costs": {"ship": {"hold": 1}, "hold": {"ship": 1}}},
}


def gate(**moves: Mapping[str, float]) -> Asker:
    """A hop that answers each value with the probabilities given for it (nothing, for one not named)."""

    async def ask(value: str) -> Mapping[str, float]:
        return moves.get(value, {})

    return ask


async def test_a_chain_of_sure_models_answers_what_none_of_them_holds() -> None:
    answer = await beam("a", [gate(a={"b": 1.0}), gate(b={"c": 1.0}), gate(c={"d": 1.0})])
    assert answer["outcome"] == "d" and answer["p"] == pytest.approx(1.0) and answer["lost"] == pytest.approx(0.0)
    assert answer["paths"] == [{"value": "d", "p": 1.0, "trail_p": 1.0, "steps": ["a", "b", "c", "d"]}]


async def test_paths_that_meet_add_up_and_the_likeliest_path_is_kept() -> None:
    first = gate(a={"x": 0.6, "y": 0.4})
    second = gate(x={"end": 0.5, "dead": 0.5}, y={"end": 1.0})
    answer = await beam("a", [first, second])
    assert answer["ends"] == {"end": pytest.approx(0.7), "dead": pytest.approx(0.3)}
    best = answer["paths"][0]
    assert (best["value"], best["steps"]) == ("end", ["a", "y", "end"]) and best["trail_p"] == pytest.approx(0.4)
    assert answer["paths"][1]["steps"] == ["a", "x", "dead"]


async def test_the_beam_keeps_only_its_width_and_the_last_hop_is_never_cut() -> None:
    first = gate(a={"x": 0.7, "y": 0.3})
    second = gate(x={"end": 1.0}, y={"other": 1.0})
    answer = await beam("a", [first, second], width=1)
    assert answer["outcome"] == "end" and answer["ends"] == {"end": pytest.approx(1.0)}
    assert answer["lost"] == pytest.approx(0.3)
    whole = await beam("a", [gate(a={"x": 0.5, "y": 0.3, "z": 0.2})], width=1)
    assert [p["value"] for p in whole["paths"]] == ["x", "y", "z"] and whole["lost"] == pytest.approx(0.0)


async def test_a_model_with_nothing_to_say_ends_the_path_or_passes_to_the_values() -> None:
    nothing = await beam("a", [gate(a={"x": 0.5, "y": 0.5}), gate(x={"end": 1.0})])
    assert nothing["ends"] == {"end": pytest.approx(1.0)} and nothing["lost"] == pytest.approx(0.5)
    gone = await beam("a", [gate()])
    assert gone == {"outcome": None, "p": 0.0, "ends": {}, "paths": [], "lost": pytest.approx(1.0)}
    spread = await beam("a", [gate(a={"x": 0.5, "y": 0.5}), gate(x={"end": 1.0})], values=["end", "other"], miss=0.2)
    # hop 1 spreads 0.2 over the values too (x, y 0.4 each; end, other 0.1 each); the three that know nothing split
    assert spread["ends"] == {"end": pytest.approx(0.66), "other": pytest.approx(0.34)}
    assert spread["lost"] == pytest.approx(0.0) and spread["outcome"] == "end"


async def test_a_beam_is_at_least_one_wide_and_miss_is_a_share() -> None:
    with pytest.raises(ValueError, match="at least 1 wide"):
        await beam("a", [gate()], width=0)
    with pytest.raises(ValueError, match="share"):
        await beam("a", [gate()], miss=1.5)


def test_a_hops_question_places_the_value_in_its_role_beside_the_fixed_ones() -> None:
    hop = Hop(model="m", role="t.s.text", fixed={"t.s.plan": "pro", "t.w.ref": "r1"}, output="team")
    asked = question(hop, "refund please")
    assert asked == {
        "data": {"t": {"s": {"plan": "pro", "text": "refund please"}, "w": {"ref": "r1"}}},
        "output": "team",
    }
    assert question(Hop(model="m", role="a.s.color"), "r") == {"data": {"a": {"s": {"color": "r"}}}}
    for role, fixed in (("color", None), ("a..color", None), ("a.s.color", {"shape": "sq"})):
        with pytest.raises(ValidationError, match="role path"):
            Hop(model="m", role=role, fixed=fixed)


def test_the_connectors_line_says_the_end_or_that_nothing_arrived() -> None:
    hops = [{"model": "a", "version": 1}, {"model": "b", "version": 2}, {"model": "c", "version": 1}]
    one = {"outcome": "ship", "p": 0.87, "ends": {"ship": 0.87, "hold": 0.08, "x": 0.05}, "lost": 0.05, "hops": hops}
    assert summary(one) == "End ship at 0.87 over 3 hops; 2 other ends; lost 0.05."
    alone = {"outcome": "ship", "p": 1.0, "ends": {"ship": 1.0}, "lost": 0.0, "hops": hops[:1]}
    assert summary(alone) == "End ship at 1.00 over 1 hop; 0 other ends; lost 0.00."
    none = {"outcome": None, "p": 0.0, "ends": {}, "lost": 1.0, "hops": hops[:2]}
    assert summary(none) == "Nothing arrived over 2 hops; lost 1.00."


def verdicts(n: int) -> list[dict[str, Any]]:
    """n graded cases for `next`: a good verdict ships, a bad one holds."""
    return [
        {
            "data": {"b": {"s": {"verdict": "good" if i % 2 else "bad", "id": f"n{i}"}}},
            "outcome": "ship" if i % 2 else "hold",
        }
        for i in range(n)
    ]


HOPS: list[dict[str, Any]] = [
    {"model": "shapes", "role": "a.s.color", "fixed": {"a.s.shape": "sq", "a.s.size": 2}},
    {"model": "next", "role": "b.s.verdict"},
]


async def test_a_beam_runs_through_two_models_and_counts_one_read_a_hop(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=60)
    await a_model(ada, key, "next", spec=NEXT)
    assert (await ada.post("/v1/models/next/record_many", json={"cases": verdicts(20)}, headers=key)).status_code == 200
    before = (await ada.get("/v1/usage", headers=key)).json()["requests"]["used"]
    got = await ada.post("/v1/beam", json={"start": "r", "hops": HOPS}, headers=key)
    assert got.status_code == 200, got.text
    answer = got.json()
    assert (
        answer["outcome"] in ("ship", "hold")
        and 0 < answer["p"] <= 1
        and sum(answer["ends"].values()) == pytest.approx(1)
    )
    assert answer["hops"] == [{"model": "shapes", "version": 1}, {"model": "next", "version": 1}]
    assert answer["ada"] == "ada-1-0" and got.headers["glyphh-ada"] == "ada-1-0"
    best = answer["paths"][0]
    assert best["value"] == answer["outcome"] and best["steps"][0] == "r" and len(best["steps"]) == 3
    assert best["steps"][1] in ("good", "bad") and best["trail_p"] <= best["p"]
    assert abs(answer["lost"]) < 0.01  # the workers round probabilities to four places
    after = (await ada.get("/v1/usage", headers=key)).json()["requests"]["used"]
    assert after - before == 2  # one read a hop, though the second hop was asked about two values
    stats = (await ada.get("/v1/models/next/stats", headers=key)).json()
    assert stats["days"][-1]["reads"]["beam"] == 1 and stats["days"][-1]["reads"]["probabilities"] == 0
    narrow = (await ada.post("/v1/beam", json={"start": "r", "hops": HOPS, "width": 1}, headers=key)).json()
    assert narrow["lost"] >= 0 and all(p["steps"][1] == narrow["paths"][0]["steps"][1] for p in narrow["paths"])
    assert sum(narrow["ends"].values()) == pytest.approx(1)


async def test_a_model_with_nothing_to_say_loses_the_path_or_passes_to_the_values(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, "blank")  # no precedents: nothing to say about anything
    await a_model(ada, key, "next", spec=NEXT)
    hops = [{"model": "blank", "role": "a.s.color"}, {"model": "next", "role": "b.s.verdict"}]
    gone = (await ada.post("/v1/beam", json={"start": "r", "hops": hops}, headers=key)).json()
    assert (gone["outcome"], gone["p"], gone["ends"], gone["paths"]) == (None, 0.0, {}, [])
    assert gone["lost"] == pytest.approx(1.0)
    assert gone["hops"] == [{"model": "blank", "version": 1}, {"model": "next", "version": 1}]  # the unasked hop too
    spread = {"start": "r", "hops": hops[:1], "values": ["good", "bad"], "miss": 0.5}
    guessed = (await ada.post("/v1/beam", json=spread, headers=key)).json()
    assert guessed["ends"] == {"good": pytest.approx(0.5), "bad": pytest.approx(0.5)} and guessed["outcome"] == "bad"


async def test_a_beam_is_refused_as_decide_is(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    _, other = await an_org(engine, ada)
    await a_model(ada, other, n=5)  # another org's shapes: not this key's
    await a_model(ada, key, "next", spec=NEXT)
    missing = await ada.post("/v1/beam", json={"start": "r", "hops": HOPS}, headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    unreached = {
        "start": "r",
        "hops": [{"model": "next", "role": "b.s.verdict"}, {"model": "nowhere", "role": "a.s.x"}],
    }
    nowhere = await ada.post("/v1/beam", json=unreached, headers=key)
    assert (nowhere.status_code, nowhere.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    for hop in ({"model": "next", "role": "verdict"}, {"model": "next", "role": "b.s.verdict", "fixed": {"id": "n1"}}):
        bad = await ada.post("/v1/beam", json={"start": "r", "hops": [hop]}, headers=key)
        assert (bad.status_code, bad.json()["error"]["code"]) == (422, "E_INVALID"), bad.text
    too_many = {"start": "r", "hops": [{"model": "next", "role": "b.s.verdict"}] * 33}
    assert (await ada.post("/v1/beam", json=too_many, headers=key)).status_code == 422
    wide = {"start": "r", "hops": HOPS[1:], "width": 51}
    assert (await ada.post("/v1/beam", json=wide, headers=key)).status_code == 422


async def test_claude_chains_models_with_ada_beam(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who = await person(engine, "Team")
    auth, key = await signed_in(engine, who), await key_for(ada, who)
    await a_model(ada, key, n=60)
    await a_model(ada, key, "next", spec=NEXT)
    await tool(ada, auth, "ada_record_many", name="next", cases=verdicts(20))
    before = (await ada.get("/v1/usage", headers=key)).json()["requests"]["used"]
    chained = await tool(ada, auth, "ada_beam", start="r", hops=HOPS)
    answer = data(chained)
    assert answer["outcome"] in ("ship", "hold") and len(answer["hops"]) == 2 and answer["ada"] == "ada-1-0"
    assert text(chained).startswith(f"End {answer['outcome']} at ") and "over 2 hops; " in text(chained)
    after = (await ada.get("/v1/usage", headers=key)).json()["requests"]["used"]
    assert after - before == 2
    hidden = await refused(ada, auth, "ada_beam", start="r", hops=[{"model": "me-000000000000-x", "role": "a.s.c"}])
    assert hidden["code"] == "E_NOT_FOUND"
    assert (await refused(ada, auth, "ada_beam", start="r", hops=[]))["code"] == "E_INVALID"
