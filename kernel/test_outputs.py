"""Named outputs: one model, one store, each case recorded once with several answers; each output learns,
calibrates and decides on its own (docs/multi-output.md)."""

from __future__ import annotations

import random

import pytest

import glyphh_kernel as kernel
from glyphh_spec import Model, Spec, SpecError

SPEC = {
    "name": "tickets",
    "seed": 5,
    "dimension": 2048,
    "layers": [
        {
            "name": "ticket",
            "segments": [
                {
                    "name": "what",
                    "roles": [
                        {"name": "product"},
                        {"name": "tier"},
                        {"name": "notes", "text_encoding": "bag_of_words"},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "outputs": {
        "team": {"values": ["billing", "login", "shipping"]},
        "urgent": {"values": ["yes", "no"], "costs": {"no": {"yes": 5}}, "ask": 0.6},
    },
}

TEAM = {"refund": "billing", "invoice": "billing", "password": "login", "locked": "login", "parcel": "shipping"}


def ticket(i: int, rng: random.Random) -> tuple[dict, dict[str, str]]:
    """The notes' telling word decides the team; the tier decides urgency; the product decides nothing."""
    word = rng.choice(sorted(TEAM))
    tier = rng.choice(["gold", "free"])
    notes = f"customer says {word} please help today"
    data = {"ticket": {"what": {"product": rng.choice(["app", "web"]), "tier": tier, "notes": notes, "id": f"t{i}"}}}
    return data, {"team": TEAM[word], "urgent": "yes" if tier == "gold" else "no"}


def tickets(n: int = 120, seed: int = 2) -> list[tuple[dict, dict[str, str]]]:
    rng = random.Random(seed)
    return [ticket(i, rng) for i in range(n)]


def model(path: str | None = None, n: int = 120, **kw) -> Model:
    m = Model(Spec.from_json(SPEC), path=path, **kw)
    for data, answers in tickets(n):
        m.record(data, outcomes=answers)
    return m


def query(word: str, tier: str) -> dict:
    return {"ticket": {"what": {"product": "app", "tier": tier, "notes": f"customer says {word} please help today", "id": "q"}}}


def test_the_spec_names_its_outputs_and_says_them_back() -> None:
    spec = Spec.from_json(SPEC)
    assert [name for name, _ in spec.outputs] == ["team", "urgent"]
    urgent = spec.output_of("urgent")
    assert urgent.values == ("yes", "no") and urgent.ask == 0.6 and urgent.cost("no", "yes") == 5
    assert spec.output_of(None) is spec.output and spec.output_of("default") is spec.output
    assert Spec.from_json(spec.to_json()) == spec
    assert "outputs" not in Spec.from_json({k: v for k, v in SPEC.items() if k != "outputs"}).to_json()
    assert Spec.from_json({**SPEC, "outputs": {"o": {}}}).to_json()["outputs"] == {"o": {}}
    assert spec.spec_id != Spec.from_json({**SPEC, "outputs": {"team": {}}}).spec_id


@pytest.mark.parametrize(
    "outputs, at",
    [
        (["team"], "outputs"),
        ({"bad name": {}}, "outputs.bad name"),
        ({"default": {}}, "outputs.default"),
        ({"o": {"values": "yes"}}, "outputs.o.values"),
        ({"o": {"values": ["a", "a"]}}, "outputs.o.values"),
        ({"o": {"values": ["a", ""]}}, "outputs.o.values"),
        ({"o": {"values": ["a"], "costs": {"a": {"b": 2}}}}, "outputs.o.costs"),
        ({"o": {"costs": {"a": 2}}}, "outputs.o.costs"),
        ({"o": {"ask": "high"}}, "outputs.o.ask"),
        ({"o": {"report": []}}, "outputs.o"),
    ],
)
def test_outputs_are_checked(outputs, at) -> None:
    with pytest.raises(SpecError) as err:
        Spec.from_json({**SPEC, "outputs": outputs})
    assert err.value.path == at


def test_a_case_is_recorded_once_with_every_answer_and_each_is_checked() -> None:
    m = model(n=12)
    assert len(m) == 12 and m.space.outputs() == ["team", "urgent"]
    data, _ = ticket(99, random.Random(9))
    with pytest.raises(SpecError, match="E_OUTPUT_VALUE"):
        m.record(data, outcomes={"team": "sales"})
    with pytest.raises(SpecError, match="E_OUTPUT:"):
        m.record(data, outcomes={"severity": "high"})
    with pytest.raises(ValueError, match="non-empty"):
        m.record(data, outcomes={"team": 3})
    with pytest.raises(SpecError, match="E_OUTPUT:"):
        m.decide(data, output="severity")
    rid = m.record(data, outcomes={"team": "login"})
    m.grade(rid, "urgent", "yes")
    m.grade(rid, "team", None)
    with pytest.raises(SpecError, match="E_OUTPUT_VALUE"):
        m.grade(rid, "urgent", "maybe")
    assert m.space.graded("urgent")[-1][1] == "yes" and len(m.space.graded("team")) == 12
    assert m.outputs() == ["team", "urgent"]
    assert Model(Spec.from_json({k: v for k, v in SPEC.items() if k != "outputs"})).outputs() == ["default"]


def test_each_output_learns_its_own_weights_and_decide_all_answers_every_question(tmp_path) -> None:
    path = str(tmp_path / "t.db")
    m = model(path)
    learned = m.learn()
    assert sorted(learned) == ["team", "urgent"]  # no default outcome: nothing to learn there
    assert learned["urgent"]["ticket.what.tier"]["similarity_weight"] == 1.0
    assert learned["urgent"]["ticket.what.product"]["similarity_weight"] < 0.1
    words = learned["team"]["ticket.what.notes"]["value_weights"]
    assert words["refund"] > 0.8 and words["customer"] == 0.35  # the telling word heard, the filler at the floor
    assert m.space.meta("learned") is None and m.space.meta("learned:team") == learned["team"]
    taus = m.calibrate()
    assert sorted(taus) == ["team", "urgent"]
    answers = m.decide_all(query("password", "gold"))
    assert {o: a["outcome"] for o, a in answers.items()} == {"team": "login", "urgent": "yes"}
    assert m.decide_all(query("parcel", "free"), outputs=["team"])["team"]["outcome"] == "shipping"
    assert m.query(query("invoice", "free"), output="team").top == "billing"
    assert m.facts(query("invoice", "free"), output="urgent", top=1)[0]["outcome"] == "no"
    m.space.close()
    for again in (Model(Spec.from_json(SPEC), path=path), Model(Spec.from_json(SPEC), path=path, readonly=True)):
        assert again.space._tau_for("team") == taus["team"]
        assert again.decide(query("locked", "gold"), output="team")["outcome"] == "login"
        assert again.decide(query("locked", "gold"), output="urgent") == m.decide(query("locked", "gold"), output="urgent")


def test_a_named_output_reads_the_store_through_its_own_view() -> None:
    m = model()
    assert m._space_for("team") is m.space  # nothing learned anywhere: the store as recorded
    m.learn("team")
    view = m._space_for("team")
    assert view is not m.space and len(view) == len(m.space)
    assert m._space_for("urgent") is m.space  # learned no words: reads the store itself
    data, answers = ticket(500, random.Random(5))
    m.record(data, outcomes=answers)
    assert m._space_for("team") is view and len(view) == len(m.space)  # the new case appended
    m.record(data, outcomes={"team": "billing"})  # the same id again: the view is made again
    again = m._space_for("team")
    assert again is not view and again.graded("team")[-1][1] == "billing"
    m.learn("team")
    assert m._space_for("team") is not again  # relearned: a new view


def test_calibrate_fits_each_output_and_the_store_keeps_it(tmp_path) -> None:
    path = str(tmp_path / "c.db")
    m = model(path)
    m.learn()
    tau = m.calibrate(output="team", by="cost")
    assert m.space._tau_for("team") == tau and m.space.meta("tau:team") == tau
    with pytest.raises(SpecError, match="loss"):
        m.calibrate(output="team", by="vibes")
    few = model(n=8)
    assert few.calibrate() == {}  # no output has ten graded precedents yet
    with pytest.raises(SpecError):
        few.learn("team")
    assert few.learn() == {}


def test_refresh_learns_and_calibrates_every_output_or_one() -> None:
    m = model()
    both = m.refresh()
    assert sorted(both) == ["team", "urgent"] and set(both["team"]) == {"learned", "tau"}
    one = m.refresh(output="urgent")
    assert set(one) == {"learned", "tau"}


def test_a_model_with_a_default_outcome_and_named_ones_learns_them_all() -> None:
    m = Model(Spec.from_json(SPEC))
    for data, answers in tickets(60):
        m.record(data, answers["urgent"], outcomes={"team": answers["team"]})
    learned = m.learn()
    assert sorted(learned) == ["default", "team"]
    assert sorted(m.calibrate()) == ["default", "team"]
    assert m.decide(query("refund", "gold"))["outcome"] == "yes"
    assert m.decide(query("refund", "gold"), output="default")["outcome"] == "yes"


def test_refresh_every_counts_cases_recorded_with_named_answers() -> None:
    m = Model(Spec.from_json(SPEC), refresh_every=20)
    for data, answers in tickets(20):
        m.record(data, outcomes=answers)
    assert m.space.meta("learned:team") is not None and m.space._taus.keys() == {"team", "urgent"}
    data, _ = ticket(77, random.Random(7))
    m.record(data)  # no answer: no refresh
    lone = Model(Spec.from_json(SPEC), refresh_every=10)
    for i in range(10):
        lone.record(ticket(i, random.Random(i))[0], outcomes={"team": "login"})  # one outcome: nothing to learn
    assert lone.space.meta("learned:team") is None


def test_a_learning_lever_moved_relearns_every_output(tmp_path) -> None:
    m = model(str(tmp_path / "l.db"))
    m.learn()
    before = m.space.meta("learned:team")
    m.configure(word_floor=0.6)
    after = m.space.meta("learned:team")
    assert after != before and min(after["ticket.what.notes"]["value_weights"].values()) >= 0.6
    assert m._specs["team"].settings.word_floor == 0.6


def test_word_evidence_is_each_outputs_own() -> None:
    m = model()
    m.learn()
    situation = m._spec_for("team").situation(query("refund", "free"))
    team = m.bias(situation, "team")
    assert team is not None and team("billing") > team("login")
    assert m.bias(situation) is None  # the default output learned nothing
    m.configure(word_evidence=0.0)
    assert m.bias(situation, "team") is None


def test_set_tau_keeps_a_temperature_and_checks_it(tmp_path) -> None:
    space = kernel.Space(path=str(tmp_path / "s.db"))
    space.set_tau("o", 0.3)
    space.set_tau(None, 0.2)
    assert space._tau_for("o") == 0.3 and space.tau == 0.2
    with pytest.raises(ValueError, match="positive"):
        space.set_tau("o", 0)
    space.close()
    again = kernel.Space(path=str(tmp_path / "s.db"))
    assert again._tau_for("o") == 0.3 and again.tau == 0.2
    memory = kernel.Space()
    memory.set_tau("o", 0.5)
    assert memory._tau_for("o") == 0.5


def test_a_view_keeps_events_ids_and_answers() -> None:
    space = kernel.Space(dim=1024)
    events = [kernel.symbol("e1", 42, 1024), kernel.symbol("e2", 42, 1024)]
    space.record({"a": "x", "b": "y"}, rid="r1", events=events, outcomes={"o": "p"})
    space.record({"a": "z", "b": "y"}, rid="r2", outcomes={"o": "q"})
    view = space.view(lambda s: {"a": s["a"]})
    assert view._ids == ["r1", "r2"] and view._situations == [{"a": "x"}, {"a": "z"}]
    assert view.graded("o") == [({"a": "x"}, "p"), ({"a": "z"}, "q")]
    assert view.query({"a": "x"}, events=events, output="o").top == "p"
    space.grade("r2", "o", "p")
    assert space.view(lambda s: {"a": s["a"]}, into=view) is view and view.graded("o")[1][1] == "p"
    other = kernel.Space(dim=1024)
    other.record({"a": "x"}, rid="r9")
    assert space.view(lambda s: s, into=other.view(lambda s: s)) is not view  # another store's view: made fresh
