"""What the store teaches the spec, and what the spec decides: learned role and value weights, the cost matrix,
the calibrated decision, and the fast weighted score equal to the fact tree's."""

from __future__ import annotations

import random

import numpy as np
import pytest

import glyphh_kernel as kernel
from glyphh_spec import Model, Spec, SpecError

SPEC = {
    "name": "loans",
    "seed": 3,
    "dimension": 2048,
    "layers": [
        {
            "name": "loan",
            "segments": [
                {
                    "name": "ask",
                    "roles": [
                        {"name": "purpose"},
                        {"name": "amount", "numeric_config": {"min_value": 0, "max_value": 10000, "bin_width": 1000}},
                        {"name": "notes", "text_encoding": "bag_of_words"},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "output": {"report": [], "costs": {"good": {"bad": 5}, "bad": {"good": 1}}},
}


def case(i: int, purpose: str, amount: int) -> dict:
    return {"loan": {"ask": {"purpose": purpose, "amount": amount, "notes": "a note", "id": f"c{i}"}}}


def cases() -> list[tuple[dict, str]]:
    """Purpose decides everything, amount nothing: cars are bad, homes good, at every amount."""
    rng = random.Random(1)
    out = []
    for i in range(200):
        purpose = rng.choice(["car", "home"])
        out.append((case(i, purpose, rng.choice([500, 2500, 7500])), "bad" if purpose == "car" else "good"))
    return out


def test_learned_weights_follow_what_decides_and_value_weights_say_which_values() -> None:
    spec = Spec.from_json(SPEC).learned(cases())
    roles = {r["name"]: r for l in spec.to_json()["layers"] for s in l["segments"] for r in s["roles"]}
    assert roles["purpose"]["similarity_weight"] == 1.0
    assert roles["amount"]["similarity_weight"] < 0.05
    assert roles["id"]["similarity_weight"] == 0 and "value_weights" not in roles["id"]  # a key part: never learned
    assert "value_weights" not in roles["notes"]  # a bag of words: the role's weight alone
    assert roles["purpose"]["value_weights"]["home"] == 1.0 and roles["purpose"]["value_weights"]["car"] > 0.8
    assert set(roles["amount"]["value_weights"]) == {"0", "2000", "7000"}
    assert Spec.from_json(spec.to_json()).to_json() == spec.to_json()  # round-trips, spec_id stable
    with pytest.raises(SpecError, match="two outcomes"):
        Spec.from_json(SPEC).learned([(case(1, "car", 500), "bad")])


def test_value_weights_change_the_weights_tree_for_the_value_present() -> None:
    obj = {**SPEC, "layers": [dict(SPEC["layers"][0])]}
    role = {"name": "purpose", "value_weights": {"car": 0.25}}
    obj["layers"][0] = {"name": "loan", "segments": [{"name": "ask", "roles": [role, {"name": "amount", "numeric_config": {"min_value": 0, "max_value": 10000, "bin_width": 1000}, "value_weights": {"2000": 0.5}}]}]}
    spec = Spec.from_json(obj)
    car = spec.situation({"loan": {"ask": {"purpose": "car", "amount": 2500}}})
    home = spec.situation({"loan": {"ask": {"purpose": "home", "amount": 500}}})
    assert spec.weights(1.0, car)["loan"]["ask"]["purpose"] == 0.25
    assert spec.weights(1.0, car)["loan"]["ask"]["amount"] == 0.5  # the bin 2000-3000, keyed by its lower edge
    assert spec.weights(1.0, home)["loan"]["ask"]["purpose"] == 1.0 and spec.weights(1.0, home)["loan"]["ask"]["amount"] == 1.0
    with pytest.raises(SpecError, match="value_weights"):
        Spec.from_json({**obj, "layers": [{"name": "loan", "segments": [{"name": "ask", "roles": [{"name": "p", "value_weights": [1]}]}]}]})


def test_costs_are_parsed_and_decide_picks_the_least_expected_cost() -> None:
    spec = Spec.from_json(SPEC)
    assert spec.output.cost("good", "bad") == 5 and spec.output.cost("bad", "good") == 1
    assert spec.output.cost("good", "good") == 0 and spec.output.cost("x", "y") == 1
    assert spec.to_json()["output"]["costs"] == {"good": {"bad": 5.0}, "bad": {"good": 1.0}}
    model = Model(spec.learned(cases()), k=15, min_sim=0.1)
    for data, outcome in cases():
        model.record(data, outcome)
    assert model.calibrate(sample=50) in kernel.TAUS
    car = model.decide(case(900, "car", 2500))
    home = model.decide(case(901, "home", 2500))
    assert car["outcome"] == "bad" and home["outcome"] == "good"
    assert car["probabilities"]["bad"] > 0.9 and home["probabilities"]["good"] > 0.9
    assert car["expected_cost"] < 0.5
    empty = Model(spec, k=5, min_sim=0.1)
    assert empty.decide(case(1, "car", 500)) == {"outcome": None, "expected_cost": None, "probabilities": {}}
    with pytest.raises(SpecError, match="costs"):
        Spec.from_json({**SPEC, "output": {"costs": {"good": 5}}})


def _situation(rng: random.Random) -> dict:
    v = lambda: rng.choice(["a", "b", 3, ["x", "y"], ["p"]])
    s = {}
    for layer in ("L1", "L2"):
        segs = {seg: {role: v() for role in ("r1", "r2", "r3") if rng.random() < 0.7} for seg in ("s1", "s2") if rng.random() < 0.8}
        segs = {k: r for k, r in segs.items() if r}
        if segs and rng.random() < 0.9:
            s[layer] = segs
    return s or {"L1": {"s1": {"r1": "a"}}}


def _weights(rng: random.Random) -> dict:
    return {
        layer: {"*": rng.choice([0.5, 1.0]), **{seg: {"*": rng.choice([0.3, 1.0]), **{role: rng.choice([0.0, 0.2, 1.0]) for role in ("r1", "r2", "r3")}} for seg in ("s1", "s2")}}
        for layer in ("L1", "L2")
    }


def test_the_fast_weighted_score_is_the_fact_trees_score() -> None:
    rng = random.Random(5)
    space = kernel.Space(dim=1024, k=10, min_sim=0.1, seed=9)
    for i in range(50):
        space.record(_situation(rng), rng.choice(["good", "bad"]), rid=f"r{i}")
    space._drop(7)
    checked = 0
    while checked < 30:
        q, w = _situation(rng), _weights(rng)
        try:
            space.encode(q, None, w)
        except ValueError:
            continue
        fast = space._fast_scores(q, w)
        exact = np.array([space._exact(i, q, None, w).score for i in range(space._n)])
        assert np.abs(fast - exact).max() < 1e-9
        checked += 1
    answer = space.query(q, weights=w)
    assert answer.count >= 0 and len(answer.receipts) <= 10
