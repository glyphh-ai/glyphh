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
    assert empty.decide(case(1, "car", 500)) == {"outcome": None, "expected_cost": None, "probabilities": {}, "ask": True}
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
        layer: {"*": rng.choice([0.5, 1.0]), **{seg: {"*": rng.choice([0.0, 0.3, 1.0]), **{role: rng.choice([0.0, 0.2, 1.0]) for role in ("r1", "r2", "r3")}} for seg in ("s1", "s2")}}
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


def test_ask_is_priced_and_decide_asks_where_every_answer_is_costly() -> None:
    obj = {**SPEC, "output": {"costs": {"good": {"bad": 5}, "bad": {"good": 1}}, "ask": 0.5}}
    spec = Spec.from_json(obj)
    assert spec.output.ask == 0.5 and spec.to_json()["output"]["ask"] == 0.5
    assert "ask" not in Spec.from_json(SPEC).to_json()["output"]
    with pytest.raises(SpecError, match="output.ask"):
        Spec.from_json({**SPEC, "output": {"ask": "cheap"}})
    rng = random.Random(2)
    model = Model(spec, k=15, min_sim=0.1)
    for i in range(120):  # cars: a coin toss; homes: always good
        purpose = rng.choice(["car", "home"])
        model.record(case(i, purpose, 2500), rng.choice(["good", "bad"]) if purpose == "car" else "good")
    model.calibrate(sample=100)
    car, home = model.decide(case(900, "car", 2500)), model.decide(case(901, "home", 2500))
    assert car["ask"] is True and car["outcome"] in ("good", "bad") and car["expected_cost"] > 0.5
    assert home["ask"] is False and home["outcome"] == "good"
    assert Model(Spec.from_json(SPEC), k=5, min_sim=0.1).decide(case(1, "car", 500))["ask"] is True  # nothing known


def test_a_model_learns_from_its_own_store_and_keeps_it_with_the_store(tmp_path) -> None:
    path = str(tmp_path / "p.sqlite")
    spec = Spec.from_json(SPEC)
    model = Model(spec, k=15, min_sim=0.1, path=path)
    with pytest.raises(SpecError, match="at least 10"):
        model.learn()
    for data, outcome in cases()[:60]:
        model.record(data, outcome)
    learned = model.learn()
    assert learned["loan.ask.purpose"]["similarity_weight"] == 1.0 and learned["loan.ask.amount"]["similarity_weight"] < 0.1
    assert "loan.ask.id" not in learned and "loan.ask.notes" not in learned
    assert model.spec.to_json() == spec.learned(cases()[:60]).to_json()  # the same as learning the cases by hand
    assert model.given is spec
    model.space.close()
    again = Model(spec, k=15, min_sim=0.1, path=path)  # reopened: the learned weights come back from the store
    assert again.spec.to_json() == model.spec.to_json() and again.space.meta("learned") == learned
    assert again.decide(case(900, "car", 2500))["outcome"] == "bad"
    again.space.close()
    fresh = Model(spec, k=15, min_sim=0.1)
    assert fresh.space.meta("learned") is None
    fresh.space.set_meta("learned", learned)
    assert fresh.space.meta("learned") == learned


def test_refresh_every_follows_the_store_as_cases_arrive() -> None:
    model = Model(Spec.from_json(SPEC), k=15, min_sim=0.1, refresh_every=50)
    for data, outcome in cases()[:49]:
        model.record(data, outcome)
    assert model.spec is model.given  # not yet
    model.record(*cases()[49])
    assert model.spec is not model.given and model.space.meta("learned")["loan.ask.purpose"]["similarity_weight"] == 1.0
    tau_50 = model.space.tau
    for data, outcome in cases()[50:100]:
        model.record(data, outcome)
    assert model.space.meta("learned") == model.given.learn(model.space.graded())
    assert model.space.tau in kernel.TAUS and tau_50 in kernel.TAUS
    same = Model(Spec.from_json(SPEC), k=15, min_sim=0.1, refresh_every=10)
    for i in range(20):
        same.record(case(i, "car", 500), "bad")  # one outcome so far: nothing to learn, nothing refused
    assert same.space.meta("learned") is None and len(same.space) == 20
    model.record(case(500, "car", 500), None)  # an ungraded case counts for nothing
    out = model.refresh(sample=30)
    assert set(out) == {"learned", "tau"} and out["tau"] == model.space.tau
    assert len(model.space.graded()) == 100


XSPEC = {
    "name": "mixed",
    "seed": 11,
    "dimension": 2048,
    "layers": [
        {
            "name": "l",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "a"},
                        {"name": "b"},
                        {"name": "c", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 5}},
                        {"name": "d"},
                        {"name": "t", "text_encoding": "bag_of_words"},
                    ],
                }
            ],
        }
    ],
    "output": {"costs": {"good": {"bad": 5}, "bad": {"good": 1}}},
}


def xcases(n: int = 300) -> list[tuple[dict, str]]:
    """b and c decide together (b=x with a low c, or b=y with a high c: good), a adds a little, d nothing."""
    rng = random.Random(4)
    out = []
    for i in range(n):
        a, b, c, d = rng.choice(["p", "q"]), rng.choice(["x", "y"]), rng.choice([2, 8]), rng.choice(["m", "n"])
        good = (b == "x") == (c < 5)
        if rng.random() < 0.1:
            good = a == "p"
        out.append(({"l": {"s": {"a": a, "b": b, "c": c, "d": d, "t": f"note {i}"}}}, "good" if good else "bad"))
    return out


def test_interactions_are_learned_from_pairs_that_tell_more_together_and_read_as_a_layer() -> None:
    spec = Spec.from_json(XSPEC).learned(xcases())
    assert [i.name for i in spec.interactions] == ["b_x_c"]
    pair = spec.interactions[0]
    assert pair.roles == ("l.s.b", "l.s.c") and pair.similarity_weight == 1.0  # the strongest signal there is
    assert set(dict(pair.value_weights)) == {"x|0", "x|5", "y|0", "y|5"}
    roles = {r["name"]: r["similarity_weight"] for l in spec.to_json()["layers"] for s in l["segments"] for r in s["roles"]}
    assert roles["b"] < 0.1 and roles["c"] < 0.1 and roles["d"] < 0.05 and 0 < roles["a"] < 0.5
    situation = spec.situation({"l": {"s": {"b": "x", "c": 7}}})
    assert situation["interactions"] == {"pairs": {"b_x_c": "x|5"}}
    assert "interactions" not in spec.situation({"l": {"s": {"b": "x", "t": "no c"}}})
    w = spec.weights(1.0, situation)
    assert w["interactions"]["pairs"]["b_x_c"] == pair.value_weight("x|5") and w["interactions"]["*"] == w["interactions"]["pairs"]["b_x_c"]
    assert spec.weights(1.0, {"l": {"s": {"b": "x"}}})["interactions"]["*"] == 0.0  # none in the situation
    again = Spec.from_json(spec.to_json())
    assert again.to_json() == spec.to_json() and again.spec_id == spec.spec_id
    assert "interactions" not in Spec.from_json(XSPEC).to_json()


def test_interactions_are_validated() -> None:
    with pytest.raises(SpecError, match="two different"):
        Spec.from_json({**XSPEC, "interactions": [{"name": "aa", "roles": ["l.s.a", "l.s.a"]}]})
    with pytest.raises(SpecError, match="roles"):
        Spec.from_json({**XSPEC, "interactions": [{"name": "ab", "roles": ["l.s.a", "l.s.zz"]}]})
    with pytest.raises(SpecError, match="must be a list"):
        Spec.from_json({**XSPEC, "interactions": {}})
    with pytest.raises(SpecError, match="the layer the spec adds"):
        Spec.from_json({**XSPEC, "layers": [{"name": "interactions", "segments": XSPEC["layers"][0]["segments"]}]})
    secured = {**XSPEC, "interactions": [{"name": "ab", "roles": ["l.s.a", "l.s.b"]}]}
    secured["layers"] = [{"name": "l", "segments": [{"name": "s", "roles": [{"name": "a", "security_weight": 0.8}, {"name": "b"}]}]}]
    spec = Spec.from_json(secured)
    situation = spec.situation({"l": {"s": {"a": "p", "b": "x"}}})
    assert situation["interactions"]["pairs"]["ab"] == "p|x"
    assert spec.weights(1.0, situation)["interactions"]["pairs"]["ab"] == 1.0
    assert spec.weights(0.5, situation)["interactions"]["pairs"]["ab"] == 0.0  # the stricter role's clearance
    assert spec.report({"key": "", "children": [{"key": "interactions", "children": []}]})["children"] == []


def test_a_model_that_learns_interactions_rewrites_its_store_and_the_pairs_decide(tmp_path) -> None:
    path = str(tmp_path / "x.sqlite")
    model = Model(Spec.from_json(XSPEC), k=15, min_sim=0.1, path=path)
    for data, outcome in xcases():
        model.record(data, outcome)
    assert all("interactions" not in s for s in model.space._situations)
    learned = model.learn()
    assert [i["name"] for i in learned["~interactions"]] == ["b_x_c"]
    assert all(s["interactions"]["pairs"]["b_x_c"] for s in model.space._situations)  # rewritten in place
    assert model.calibrate(sample=100) in kernel.TAUS
    right = sum(model.decide(data)["outcome"] == outcome for data, outcome in xcases()[:100])
    assert right >= 85
    model.space.close()
    again = Model(Spec.from_json(XSPEC), k=15, min_sim=0.1, path=path)
    assert [i.name for i in again.spec.interactions] == ["b_x_c"]
    assert again.space._situations[0]["interactions"] == model.space._situations[0]["interactions"]
    assert again.space.rewrite(again.spec.recross) == 0  # nothing to change
    again.space.close()


def test_calibrate_by_cost_picks_the_temperature_that_decides_best() -> None:
    model = Model(Spec.from_json(XSPEC), k=15, min_sim=0.1)
    for data, outcome in xcases(120):
        model.record(data, outcome)
    model.learn()
    by_loss, by_cost = model.calibrate(sample=100, by="loss"), model.calibrate(sample=100, by="cost")
    assert by_loss in kernel.TAUS and by_cost in kernel.TAUS
    assert model.refresh(sample=50, by="cost")["tau"] == model.space.tau
    with pytest.raises(SpecError, match="by"):
        model.calibrate(by="accuracy")
    space = model.space
    seen: list[tuple[dict[str, float], str]] = []

    def dear(p: dict[str, float], true: str) -> float:  # a cost of its own: the mass on the wrong outcomes, squared
        seen.append((p, true))
        return sum(q for o, q in p.items() if o != true) ** 2

    chosen = space.calibrate(sample=50, cost=dear)
    assert len(seen) == 50 * len(kernel.TAUS)
    totals = {}
    held = [i for i in range(space._n) if space._outcomes[i] is not None][-50:]
    for tau in kernel.TAUS:
        totals[tau] = sum(dear(space._probabilities(space._scores(space._situations[h], None, {}), tau, skip=h), space._outcomes[h]) for h in held)
    assert totals[chosen] == min(totals.values())
    flat = space.calibrate(sample=50, cost=lambda p, true: 0.0)  # all tied on cost: log-loss decides
    assert flat == space.calibrate(sample=50)


def test_rewrite_keeps_events_and_the_fast_score(tmp_path) -> None:
    space = kernel.Space(dim=1024, k=5, min_sim=0.1, seed=3, path=str(tmp_path / "e.sqlite"))
    ev = [kernel.symbol("e1", 3, 1024), kernel.symbol("e2", 3, 1024)]
    space.record({"a": {"b": {"c": "one"}}}, "yes", events=ev, rid="r1")
    space.record({"a": {"b": {"c": "two"}}}, "no", rid="r2")
    before = space._glyphs[0].copy()
    assert space.rewrite(lambda s: {**s, "z": {"y": {"x": s["a"]["b"]["c"] + "!"}}}) == 2
    assert space._situations[1] == {"a": {"b": {"c": "two"}}, "z": {"y": {"x": "two!"}}}
    assert kernel.sim(space._glyphs[0], before) > 0.3 and space._trajs[0] is not None
    assert space.query({"a": {"b": {"c": "two"}}, "z": {"y": {"x": "two!"}}}, weights={"a": 1.0, "z": 0.5}).top == "no"
    space.close()
    again = kernel.Space(dim=1024, k=5, min_sim=0.1, seed=3, path=str(tmp_path / "e.sqlite"))
    assert again._situations[1]["z"] == {"y": {"x": "two!"}} and again._trajs[0] is not None
    bare = kernel.Space(dim=1024, k=5, min_sim=0.1, seed=3)
    bare.record({"a": {"b": {"c": "one"}}}, "yes", events=ev)
    assert bare.rewrite(lambda s: {**s, "q": {"r": {"s": "t"}}}) == 1 and bare._trajs[0] is not None
    plain = kernel.Space(dim=1024, k=5, min_sim=0.1, seed=3)
    plain.record({"a": {"b": {"c": "one"}}}, "yes")
    plain.record({"a": {"b": {"c": "two"}}}, "no")
    plain.rewrite(lambda s: {**s, "z": {"y": {"x": s["a"]["b"]["c"] + "!"}}})
    q, w = {"a": {"b": {"c": "one"}}, "z": {"y": {"x": "one!"}}}, {"a": 1.0, "z": 0.5}
    fast = plain._fast_scores(q, w)
    exact = [plain._exact(i, q, None, w).score for i in range(2)]
    assert np.abs(fast - np.array(exact)).max() < 1e-9 and fast[0] > 0.99  # the leaf tables were rebuilt


TSPEC = {
    "name": "notes",
    "seed": 5,
    "dimension": 2048,
    "layers": [{"name": "m", "segments": [{"name": "b", "roles": [{"name": "text", "text_encoding": "bag_of_words"}, {"name": "id", "key_part": True, "similarity_weight": 0}]}]}],
}


def tcases(n: int = 200) -> list[tuple[dict, str]]:
    """'stolen' or 'lost' says card_lost, 'rate' or 'exchange' says fx; the rest of the words are filler shared by all."""
    rng = random.Random(8)
    filler = ["my", "card", "please", "help", "i", "the", "what", "about", "can", "you"]
    out = []
    for i in range(n):
        label = rng.choice(["card_lost", "fx"])
        key = rng.choice(["stolen", "lost"]) if label == "card_lost" else rng.choice(["rate", "exchange"])
        text = " ".join(rng.sample(filler, 4) + [key])
        out.append(({"m": {"b": {"text": text, "id": f"t{i}"}}}, label))
    return out


def test_a_weighted_set_encodes_by_its_weights() -> None:
    plain = kernel.encode(["a", "b"], seed=1, dim=1024)
    assert np.array_equal(kernel.encode([["a", 1.0], ["b", 1.0]], seed=1, dim=1024), plain)  # equal weights: a set
    heavy = kernel.encode([["a", 1.0], ["b", 0.02]], seed=1, dim=1024)
    assert kernel.sim(heavy, kernel.symbol("val:a", 1, 1024)) > 0.95 > kernel.sim(plain, kernel.symbol("val:a", 1, 1024))
    assert np.array_equal(kernel.encode([["a", 0.0], ["b", 0.0]], seed=1, dim=1024), plain)  # all voiceless: a set
    pairs = kernel.encode([["a", 2], ["b", 3]], seed=1, dim=1024)  # weights over 1: a set of pairs, as before
    assert not np.array_equal(pairs, plain) and kernel.sim(pairs, kernel.encode([["a", 2]], seed=1, dim=1024)) > 0.3


def test_words_are_learned_and_the_bag_carries_them() -> None:
    spec = Spec.from_json(TSPEC).learned(tcases())
    role = spec.layers[0].segments[0].roles[0]
    table = dict(role.value_weights)
    assert {w for w, v in table.items() if v == 1.0} <= {"stolen", "lost", "rate", "exchange"} and 1.0 in table.values()
    assert all(0.35 <= table[w] <= 0.6 for w in ("my", "card", "please", "help"))
    assert role.similarity_weight == 1.0  # a text role's own weight is not learned
    situation = spec.situation({"m": {"b": {"text": "my stolen card", "id": "x"}}})
    assert situation["m"]["b"]["text"] == [["card", table["card"]], ["my", table["my"]], ["stolen", table["stolen"]]] and table["stolen"] > 0.8
    assert spec.situation({"m": {"b": {"text": "zebra", "id": "x"}}})["m"]["b"]["text"] == [["zebra", 0.35]]
    assert Spec.from_json(TSPEC).situation({"m": {"b": {"text": "my stolen card", "id": "x"}}})["m"]["b"]["text"] == ["card", "my", "stolen"]
    assert Spec.from_json(spec.to_json()).to_json() == spec.to_json()
    assert spec.key(situation) == Spec.from_json(TSPEC).key(situation)


def test_a_model_that_learns_words_rewrites_its_store_and_routes_better(tmp_path) -> None:
    path = str(tmp_path / "t.sqlite")
    model = Model(Spec.from_json(TSPEC), k=15, min_sim=0.05, path=path)
    for data, outcome in tcases():
        model.record(data, outcome)
    probe = [({"m": {"b": {"text": "help my card the stolen", "id": "p1"}}}, "card_lost"), ({"m": {"b": {"text": "what about the exchange", "id": "p2"}}}, "fx")]
    before = [model.query(d).top == o for d, o in probe]
    learned = model.learn()
    assert "value_weights" in learned["m.b.text"] and "similarity_weight" not in learned["m.b.text"]
    assert all(isinstance(s["m"]["b"]["text"][0], list) for s in model.space._situations)  # rewritten with weights
    assert all(model.query(d).top == o for d, o in probe) and sum(before) <= 2
    model.space.close()
    again = Model(Spec.from_json(TSPEC), k=15, min_sim=0.05, path=path)
    assert dict(again.spec.layers[0].segments[0].roles[0].value_weights) == learned["m.b.text"]["value_weights"]
    assert again.space.rewrite(again.spec.restate) == 0
    again.space.close()
    assert Spec.from_json(TSPEC).learned(tcases()).to_json() == Spec.from_json(TSPEC).with_weights(learned).to_json()
