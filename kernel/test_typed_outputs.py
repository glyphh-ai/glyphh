"""Typed outputs (kernel 3.15.0): an output's kind (choice, score, noul, number, many) and a discriminated union
(`when`: an output asked only when another's outcome is one of some values)."""

from __future__ import annotations

import random

import pytest

from glyphh_spec import Model, Spec, SpecError

ROLES = [
    {"name": "tier"},
    {"name": "product"},
    {"name": "notes", "text_encoding": "bag_of_words"},
    {"name": "id", "key_part": True, "similarity_weight": 0},
]
OUTPUTS = {
    "kind": {"values": ["bug", "billing"]},
    "severity": {"kind": "score", "values": ["low", "medium", "high"], "when": {"output": "kind", "in": ["bug"]}},
    "refund": {"kind": "number", "number": {"min": 0, "max": 100, "step": 10}, "when": {"output": "kind", "in": ["billing"]}},
    "urgent": {"kind": "noul"},
    "tags": {"kind": "many", "values": ["mobile", "web", "gold"]},
}
SPEC = {
    "name": "typed",
    "seed": 5,
    "dimension": 2048,
    "layers": [{"name": "t", "segments": [{"name": "s", "roles": ROLES}]}],
    "outputs": OUTPUTS,
}


def case(i: int, rng: random.Random) -> tuple[dict, dict]:
    """The notes say the kind; a bug's severity and a billing case's refund follow the tier; tags the product."""
    kind = rng.choice(["bug", "billing"])
    tier, product = rng.choice(["gold", "free"]), rng.choice(["mobile", "web"])
    notes = "app crashes on start" if kind == "bug" else "charged twice this month"
    data = {"t": {"s": {"tier": tier, "product": product, "notes": notes, "id": f"c{i}"}}}
    answers: dict = {"kind": kind, "urgent": tier == "gold", "tags": [product, *(["gold"] if tier == "gold" else [])]}
    if kind == "bug":
        answers["severity"] = "high" if tier == "gold" else "low"
    else:
        answers["refund"] = 80 if tier == "gold" else 15
    return data, answers


def model() -> Model:
    rng = random.Random(3)
    m = Model(Spec.from_json(SPEC), path=None)
    for i in range(120):
        data, answers = case(i, rng)
        m.record(data, outcomes=answers)
    m.refresh()
    return m


def query(notes: str, tier: str, product: str = "web") -> dict:
    return {"t": {"s": {"tier": tier, "product": product, "notes": notes, "id": "q"}}}


def test_the_spec_says_its_kinds_back_and_hides_a_many_outputs_members() -> None:
    spec = Spec.from_json(SPEC)
    assert spec.declared() == ["kind", "refund", "severity", "tags", "urgent"]
    assert [n for n in spec.stored() if n.startswith("tags")] == ["tags--0", "tags--1", "tags--2"]
    assert spec.output_of("refund").values[:2] == ("5", "15")
    assert Spec.from_json(spec.to_json()).to_json() == spec.to_json()
    assert spec.to_json()["outputs"]["urgent"] == {"kind": "noul"}


@pytest.mark.parametrize(
    "outputs, at",
    [
        ({"x": {"kind": "vector"}}, "outputs.x.kind"),
        ({"x": {"kind": "score", "values": ["one"]}}, "outputs.x.values"),
        ({"x": {"kind": "noul", "values": ["yes", "no"]}}, "outputs.x.values"),
        ({"x": {"kind": "number", "number": {"min": 1, "max": 0, "step": 1}}}, "outputs.x.number"),
        ({"x": {"kind": "number", "values": ["1"], "number": {"min": 0, "max": 1, "step": 1}}}, "outputs.x.values"),
        ({"x": {"values": ["a"], "number": {"min": 0, "max": 1, "step": 1}}}, "outputs.x.number"),
        ({"x": {"values": ["a"], "when": {"output": "y", "in": ["a"]}}}, "outputs.x.when.output"),
        ({"x": {"values": ["a"]}, "y": {"values": ["b"], "when": {"output": "x", "in": ["z"]}}}, "outputs.y.when.in"),
        (
            {"x": {"values": ["a"], "when": {"output": "y", "in": ["b"]}}, "y": {"values": ["b"], "when": {"output": "x", "in": ["a"]}}},
            "outputs.x.when",
        ),
        ({"x": {"kind": "many", "values": ["a", "b"], "ask": 0.5}}, "outputs.x"),
    ],
)
def test_a_typed_output_is_checked(outputs: dict, at: str) -> None:
    with pytest.raises(SpecError) as err:
        Spec.from_json({**SPEC, "outputs": outputs})
    assert err.value.path == at


def test_outcomes_are_typed_when_recorded() -> None:
    m = Model(Spec.from_json(SPEC), path=None)
    data, _ = case(0, random.Random(1))
    with pytest.raises(SpecError, match="E_OUTPUT_WHEN"):
        m.record(data, outcomes={"kind": "billing", "severity": "high"})
    with pytest.raises(SpecError, match="E_OUTPUT_VALUE"):
        m.record(data, outcomes={"tags": ["mobile", "tablet"]})
    with pytest.raises(SpecError, match="E_OUTPUT_VALUE"):
        m.record(data, outcomes={"severity": "huge"})
    rid = m.record(data, outcomes={"kind": "billing", "refund": 42.5, "urgent": True, "tags": ["web"]})
    m.grade(rid, "tags", ["gold"])
    m.grade(rid, "refund", 100)
    stored = m.space.outputs()
    assert {"refund", "urgent", "tags--0", "tags--2"} <= set(stored) and "tags" not in stored
    m.grade(rid, "tags", None)  # taken away: every member's
    assert [len(m.space.graded(f"tags--{i}")) for i in range(3)] == [0, 0, 0] and len(m.space.graded("refund")) == 1


def test_each_kind_decides_in_its_own_terms_and_the_union_branches() -> None:
    m = model()
    bug = m.decide_all(query("app crashes on start", "gold", "mobile"))
    assert bug["kind"]["outcome"] == "bug"
    assert bug["severity"]["applies"] and bug["severity"]["outcome"] == "high" and bug["severity"]["level"] > 1
    assert bug["refund"] == {"outcome": None, "expected_cost": None, "probabilities": {}, "ask": False, "applies": False}
    assert bug["urgent"]["outcome"] == "true" and bug["urgent"]["p"] > 0.5
    assert set(bug["tags"]["outcome"]) == {"mobile", "gold"}
    billing = m.decide_all(query("charged twice this month", "free"), outputs=["refund"])
    assert billing["refund"]["applies"] and billing["refund"]["outcome"] == "15"
    assert 5 <= billing["refund"]["value"] <= 30
    assert set(m.probabilities(query("charged twice this month", "free"), output="tags")) == {"mobile", "web", "gold"}


def test_a_score_mistake_costs_the_levels_it_is_off() -> None:
    o = Spec.from_json(SPEC).output_of("severity")
    assert (o.cost("low", "high"), o.cost("medium", "high"), o.cost("high", "high")) == (2.0, 1.0, 0.0)
    plain = Spec.from_json({**SPEC, "outputs": {"s": {"values": ["low", "medium", "high"]}}}).output_of("s")
    assert plain.cost("low", "high") == 1.0  # a choice's mistakes all cost the same, as before
