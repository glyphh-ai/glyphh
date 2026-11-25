"""The thread: a model's cases in the order they happened, read ahead (predict) and back (lookback)."""

from __future__ import annotations

import pytest

from glyphh_kernel import Space
from glyphh_spec import Model, Spec, SpecError

SPEC = {
    "name": "ring",
    "seed": 5,
    "dimension": 1024,
    "layers": [{"name": "h", "segments": [{"name": "s", "roles": [{"name": "at"}, {"name": "who"}]}]}],
}
RING = "abcd"


def case(at: str, who: str = "x") -> dict:
    return {"h": {"s": {"at": at, "who": who}}}


def ring(turns: int = 10, who: str = "x", start: float = 0.0, model: Model | None = None) -> Model:
    """a, b, c, d, a, ... each case's outcome the place it is at."""
    model = Model(Spec.from_json(SPEC)) if model is None else model  # an empty model is falsy
    for i in range(turns * len(RING)):
        model.record(case(RING[i % 4], who), RING[i % 4], ts=start + i)
    return model


def test_predict_reads_what_followed_the_cases_like_this_one() -> None:
    answer = ring().predict(case("a"), 3)
    assert [s["step"] for s in answer["steps"]] == [1, 2, 3]
    assert [s["outcome"] for s in answer["steps"]] == ["b", "c", "d"]
    assert all(s["p"] > 0.9 for s in answer["steps"])
    assert answer["halted"] is None and answer["lost"] == 0.0


def test_lookback_reads_what_came_before() -> None:
    answer = ring().lookback(case("a"), 3)
    assert [s["outcome"] for s in answer["steps"]] == ["d", "c", "b"]


def test_a_list_of_steps_answers_those_steps_alone() -> None:
    answer = ring().predict(case("a"), [2, 5])
    assert [(s["step"], s["outcome"]) for s in answer["steps"]] == [(2, "c"), (5, "b")]


def test_each_thread_is_read_along_its_own_cases() -> None:
    model = ring(who="x")
    for i in range(40):  # y walks the ring the other way, its cases landing between x's in time
        model.record(case(RING[-(i % 4) - 1], "y"), RING[-(i % 4) - 1], ts=i + 0.5)
    assert model.predict(case("a", "x"), 1, thread="h.s.who")["steps"][0]["outcome"] == "b"
    assert model.predict(case("a", "y"), 1, thread="h.s.who")["steps"][0]["outcome"] == "d"
    with pytest.raises(SpecError):
        model.predict(case("a"), 1, thread="h.s.nobody")


def test_before_reads_nothing_from_that_time_on() -> None:
    model = Model(Spec.from_json(SPEC))
    for i in range(40):  # the ring turns one way, then (from time 40) the other
        model.record(case(RING[i % 4]), RING[i % 4], ts=i)
    for i in range(40):
        model.record(case(RING[-(i % 4) - 1]), RING[-(i % 4) - 1], ts=40 + i)
    assert model.predict(case("b"), 1, before=40)["steps"][0]["outcome"] == "c"
    assert model.predict(case("b"), 1, before=40)["steps"][0]["p"] > 0.9
    assert model.predict(case("b"), 1)["steps"][0]["p"] < 0.9  # both turnings are read
    assert model.predict(case("b"), 1, before=0) == {"steps": [], "halted": 1, "lost": 0.0}


def test_the_beam_arrives_where_each_step_read_alone_does() -> None:
    model = ring()
    alone, beam = model.predict(case("a"), 6), model.predict(case("a"), 6, chain=True)
    assert [s["outcome"] for s in beam["steps"]] == [s["outcome"] for s in alone["steps"]] == list("bcdabc")
    assert beam["lost"] == pytest.approx(0.0, abs=1e-9)  # cases in the same situation go on as one


def test_a_narrow_beam_says_what_it_cut() -> None:
    model = Model(Spec.from_json(SPEC))
    t = 0
    for nxt in ("b", "c", "d") * 10:  # from a: b, c or d, each a third of the time, and each goes on to itself
        for at in ("a", nxt, nxt):
            model.record(case(at), at, ts=(t := t + 1))
    wide = model.predict(case("a"), 2, chain=True)
    narrow = model.predict(case("a"), 2, chain=True, width=1)
    assert wide["lost"] == pytest.approx(0.0, abs=1e-9) and narrow["lost"] > 0.3
    with pytest.raises(ValueError):
        model.predict(case("a"), 2, chain=True, width=0)


def test_halt_stops_at_the_first_step_that_says_too_little() -> None:
    model = Model(Spec.from_json(SPEC))
    t = 0
    for i in range(60):  # a is always followed by b; what follows b is one of four, evenly
        for at in ("a", "b", RING[i % 4]):
            model.record(case(at), at, ts=(t := t + 1))
    answer = model.predict(case("a"), 4, halt=0.5)
    assert [s["outcome"] for s in answer["steps"]] == ["b"]
    assert answer["halted"] == 2
    assert len(model.predict(case("a"), 4)["steps"]) == 4  # without a halt every step is answered


def test_every_case_in_the_same_situation_speaks() -> None:
    model = Model(Spec.from_json(SPEC))
    t = 0
    for i in range(200):  # after a: b three times in four, the older cases as much as the newest
        for at in ("a", "b" if i % 4 else "c"):
            model.record(case(at), at, ts=(t := t + 1))
    p = model.predict(case("a"), 1)["steps"][0]["probabilities"]
    assert p["b"] == pytest.approx(0.75, abs=0.01) and p["c"] == pytest.approx(0.25, abs=0.01)


def test_learn_thread_weighs_what_tells_the_next_step_and_is_kept(tmp_path) -> None:
    path = str(tmp_path / "ring.sqlite")
    model = ring(model=Model(Spec.from_json(SPEC), path=path))
    with pytest.raises(SpecError):
        Model(Spec.from_json(SPEC)).learn_thread()
    kept = model.learn_thread()
    assert kept["learned"]["h.s.at"]["similarity_weight"] == 1.0  # where it is tells where it goes; who does not
    assert kept["learned"]["h.s.who"]["similarity_weight"] < 0.1
    back = model.learn_thread(back=True)
    model.space.close()
    again = Model(Spec.from_json(SPEC), path=path)
    assert again.space._taus == {"default>": kept["tau"], "default<": back["tau"]}
    assert again.predict(case("a"), 2)["steps"][1]["outcome"] == "c"
    assert again.lookback(case("a"), 2)["steps"][1]["outcome"] == "c"


def test_the_kernel_reads_a_thread_without_a_spec() -> None:
    space = Space(dim=1024)
    for i in range(40):
        space.record({"at": RING[i % 4]}, RING[i % 4], ts=i)
    assert [s["outcome"] for s in space.predict({"at": "a"}, 2)["steps"]] == ["b", "c"]
    assert [s["outcome"] for s in space.lookback({"at": "a"}, 2)["steps"]] == ["d", "c"]
    assert space.followed(steps=2)[0][1] == "c" and len(space.followed(steps=2)) == 38
    with pytest.raises(ValueError):
        space.predict({"at": "a"}, 0)
    assert Space(dim=1024).predict({"at": "a"}, 1) == {"steps": [], "halted": 1, "lost": 0.0}
