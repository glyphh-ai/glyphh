"""Beam search across models (kernel 3.17.0): one model's outcome is the next one's question."""

from __future__ import annotations

import pytest

from glyphh_spec import Hop, Model, Spec, beam

SPEC = {
    "name": "hop",
    "seed": 5,
    "dimension": 1024,
    "layers": [{"name": "h", "segments": [{"name": "s", "roles": [{"name": "at"}]}]}],
}


def ask(value: str) -> dict:
    return {"h": {"s": {"at": value}}}


def gate(*moves: tuple[str, str]) -> Hop:
    model = Model(Spec.from_json(SPEC))
    for at, to in moves:
        model.record(ask(at), to)
    return Hop(model, ask)


def test_a_chain_of_sure_models_answers_what_none_of_them_holds() -> None:
    answer = beam("a", [gate(("a", "b")), gate(("b", "c")), gate(("c", "d"))])
    assert answer["outcome"] == "d" and answer["p"] == pytest.approx(1.0)
    assert answer["paths"][0]["steps"] == ["a", "b", "c", "d"]


def test_an_unsure_first_step_is_settled_by_the_steps_after_it() -> None:
    first = gate(("a", "x"), ("a", "x"), ("a", "y"))
    second = gate(("x", "dead"), ("y", "end"))
    p = first.model.probabilities(ask("a"))
    answer = beam("a", [first, second])
    assert answer["ends"]["dead"] == pytest.approx(p["x"], abs=0.02)
    assert answer["ends"]["end"] == pytest.approx(p["y"], abs=0.02)


def test_paths_that_meet_add_up_and_the_likeliest_path_is_kept() -> None:
    first = gate(("a", "x"), ("a", "y"))
    second = gate(("x", "end"), ("y", "end"))
    answer = beam("a", [first, second])
    assert answer["ends"] == {"end": pytest.approx(1.0)}
    assert answer["paths"][0]["trail_p"] < answer["paths"][0]["p"]


def test_the_beam_keeps_only_its_width_and_says_what_it_cut() -> None:
    first = gate(("a", "x"), ("a", "x"), ("a", "y"))
    second = gate(("x", "end"), ("y", "other"))
    answer = beam("a", [first, second], width=1)
    assert answer["outcome"] == "end" and all(path["steps"][1] == "x" for path in answer["paths"])
    assert answer["lost"] > 0


def test_the_last_hop_is_never_cut() -> None:
    answer = beam("a", [gate(("a", "x"), ("a", "y"), ("a", "z"))], width=1)
    assert set(answer["ends"]) == {"x", "y", "z"} and answer["lost"] == pytest.approx(0.0)


def test_a_model_with_nothing_to_say_ends_the_path() -> None:
    answer = beam("a", [gate(("a", "b")), gate()])
    assert answer["outcome"] is None and answer["p"] == 0.0 and answer["ends"] == {} and answer["paths"] == []
    assert answer["lost"] == pytest.approx(1.0)


def test_values_carry_a_chain_through_a_model_that_does_not_know() -> None:
    answer = beam("a", [gate(("a", "b")), gate(), gate(("x", "end"))], values=["x", "y"])
    assert answer["ends"]["end"] > 0 and answer["lost"] == pytest.approx(0.0)


def test_miss_leaks_a_share_of_every_hop_over_the_values() -> None:
    answer = beam("a", [gate(("a", "b"))], values=["b", "c"], miss=0.1)
    assert answer["ends"]["b"] == pytest.approx(0.95) and answer["ends"]["c"] == pytest.approx(0.05)


def test_no_hops_answers_the_start() -> None:
    assert beam("a", [])["outcome"] == "a"


def test_a_named_output_is_read() -> None:
    spec = SPEC | {"outputs": {"next": {"values": ["b", "c"]}}}
    model = Model(Spec.from_json(spec))
    model.record(ask("a"), outcomes={"next": "c"})
    assert beam("a", [Hop(model, ask, "next")])["outcome"] == "c"


@pytest.mark.parametrize("kwargs", [{"width": 0}, {"miss": -0.1}, {"miss": 1.5}])
def test_a_bad_beam_is_refused(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        beam("a", [], **kwargs)
