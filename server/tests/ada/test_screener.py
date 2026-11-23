"""The Resume Screener's gates on real Ada (the kernel, through Ada Cloud's API and its worker): each gate's model made
from the template's spec, its seed set's train split recorded, its test split decided as new applicants, a verdict
corrected and learned, and the generated gate probed: its reference measured over the test split's generated
applicants as the template does at seeding, then the test split's human applicants (which no gate ever holds) found
by having no generated precedent as close. Its bars are the template's promise that the seed set teaches its gates
something: they are what Ada scores from these precedents alone, before any person's answer."""

import copy
from typing import Any

import httpx
from glyphh.bots.runner import fill
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from glyphh_server.ops.bots import packages, probe, seeds
from tests.ada.conftest import an_org

BARS: dict[str, float] = {"source": 0.9, "fit": 0.6, "made": 0.6, "human": 0.6}


def _gate(name: str) -> dict[str, Any]:
    """The gate as the template ships it: a copy, so nothing done with it reaches the library the process keeps."""
    return copy.deepcopy(packages.library()["resume-screener"].sidecar.decisions[name])


def _humans() -> list[dict[str, Any]]:
    """The test split's applicants written by people, as the generated gate's cases."""
    gate = _gate("made")
    return [{"data": fill(gate["case"], {"item": item})} for item, labels, split in seeds.items("resume-screener")
            if split == "test" and labels.get("source") == "real" and "made" not in labels]  # fmt: skip


async def _decide(ada: httpx.AsyncClient, key: dict[str, str], name: str, case: dict[str, Any]) -> dict[str, Any]:
    got = await ada.post(f"/v1/models/{name}/decide", json={"data": case["data"]}, headers=key)
    assert got.status_code == 200, got.text
    return dict(got.json())


def _near(decided: dict[str, Any]) -> float:
    return max(float(r["sim"]) for r in decided["receipts"])


async def _scored(ada: httpx.AsyncClient, key: dict[str, str], name: str) -> tuple[float, list[Any]]:
    gate = _gate(name)
    known, new = seeds.cases(gate, name), seeds.cases(gate, name, "test")
    made = await ada.post("/v1/models", json={"name": name, "spec": gate["spec"]}, headers=key)
    assert made.status_code == 201, made.text
    done = await ada.post(f"/v1/models/{name}/record_many", json={"cases": known}, headers=key)
    assert done.status_code == 200 and done.json()["added"] == len(known), done.text
    calls = [(c, await _decide(ada, key, name, c)) for c in new]
    right = sum(1 for c, d in calls if d["outcome"] == c["outcome"])
    return right / len(new), calls


async def test_the_seed_set_teaches_each_gate_and_a_correction_is_learned(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    scores, calls = {}, {}
    for name in ("source", "fit", "made"):
        scores[name], calls[name] = await _scored(ada, key, name)
    reference = probe.spread([_near(d) for _, d in calls["made"]])
    humans = [_near(await _decide(ada, key, "made", c)) for c in _humans()]
    scores["human"] = sum(1 for s in humans if s < reference["p5"]) / len(humans)
    print(f"scores {scores}; reference {reference}; humans' nearest {sorted(humans)}")
    assert all(scores[n] >= bar for n, bar in BARS.items()), (scores, reference, humans)
    case, said = next((c, d) for c, d in calls["fit"] if d["outcome"] != c["outcome"])  # corrected as a person would
    fixed = await ada.post("/v1/models/fit/record", json=case, headers=key)
    assert fixed.status_code == 200, fixed.text
    assert (await _decide(ada, key, "fit", case))["outcome"] == case["outcome"] != said["outcome"]
