"""The release says the same everywhere (CHANGELOG.md, the rule), and 3.13.0's one answer-changing change."""

from __future__ import annotations

import random
import re
import tomllib
from pathlib import Path

import glyphh_kernel as kernel
import glyphh_postgres
from glyphh_spec import Model, Spec
from test_learned import XSPEC, xcases

HERE = Path(__file__).parent


def _releases() -> list[tuple[str, str]]:
    text = (HERE / "CHANGELOG.md").read_text()
    return re.findall(r"^## (\d+\.\d+\.\d+) — \d{4}-\d{2}-\d{2} — (answer-changing|compatible)$", text, re.M)


def test_the_version_is_one_number_in_the_kernel_the_package_and_the_changelog() -> None:
    project = tomllib.loads((HERE / "pyproject.toml").read_text())["project"]
    assert kernel.__version__ == project["version"] == _releases()[0][0]
    assert glyphh_postgres.STORE_FORMAT == 1


def test_every_release_says_whether_it_changes_answers_and_patches_never_do() -> None:
    releases = _releases()
    assert len(releases) >= 13
    for (newer, kind), (older, _) in zip(releases, releases[1:]):
        new, old = [tuple(int(x) for x in v.split(".")) for v in (newer, older)]
        assert new > old, f"{newer} is listed above {older}"
        if new[:2] == old[:2]:  # a patch
            assert kind == "compatible", f"{newer} changes answers: it must be a minor"


def test_a_pair_value_never_learned_weighs_nothing_so_the_roles_decide() -> None:
    spec = Spec.from_json(XSPEC).learned(xcases())
    pair = spec.interactions[0]
    assert pair.value_weight("x|5") > 0 and pair.value_weight("z|5") == 0.0  # z: a b value never seen
    assert Spec.from_json(XSPEC).interactions == ()  # nothing learned: no pairs to weigh
    seen = spec.weights(1.0, spec.situation({"l": {"s": {"a": "p", "b": "x", "c": 7}}}))
    new = spec.weights(1.0, spec.situation({"l": {"s": {"a": "p", "b": "z", "c": 7}}}))
    assert seen["interactions"]["*"] > 0
    assert new["interactions"]["pairs"]["b_x_c"] == 0.0 and new["interactions"]["*"] == 0.0  # out of the mean

    model = Model(spec, path=None, author="t")
    for situation, outcome in xcases():
        model.record(situation, outcome)
    answer = model.query({"l": {"s": {"a": "p", "b": "z", "c": 7}}})
    assert answer.top is not None  # the roles' own weights still find neighbours: an answer, not nothing


# 3.14.0: levels weigh by their roles, and calibrate fits a recency half-life

LEVELS = {
    "name": "levels",
    "seed": 5,
    "dimension": 1024,
    "layers": [
        {
            "name": "l",
            "segments": [
                {"name": "a", "roles": [{"name": "signal"}]},
                {"name": "b", "roles": [{"name": f"noise{i}"} for i in range(4)]},
            ],
        }
    ],
}


def _levels(n: int = 200) -> list[tuple[dict, str]]:
    rng = random.Random(4)
    out = []
    for _ in range(n):
        signal = rng.choice(["x", "y"])
        noise = {f"noise{i}": rng.choice(["p", "q"]) for i in range(4)}
        out.append(({"l": {"a": {"signal": signal}, "b": noise}}, "yes" if signal == "x" else "no"))
    return out


def test_level_weights_roles_makes_a_segment_weigh_what_its_roles_weigh_so_learned_noise_goes_quiet() -> None:
    old = Spec.from_json(LEVELS).learned(_levels())
    assert old.settings.level_weights == "spec"  # the default: answers as before 3.14.0
    spec = old.with_settings(old.settings.with_changes({"level_weights": "roles"}))
    query = {"l": {"a": {"signal": "x"}, "b": {f"noise{i}": "p" for i in range(4)}}}
    tree = spec.weights(1.0, spec.situation(query))
    assert tree["l"]["a"]["*"] > 0.8 and tree["l"]["b"]["*"] < 0.1  # the noise segment's roles learned ~0
    assert tree["l"]["*"] == tree["l"]["a"]["*"] + tree["l"]["b"]["*"]
    assert old.weights(1.0, old.situation(query))["l"]["b"]["*"] == 1.0  # by the spec: the segment speaks whole

    def sure(s: Spec) -> float:
        """The mean probability a held-out case gets for its true outcome, over a store small enough that every
        precedent is in the softmax: the noise segment's pull on the other outcome's precedents shows."""
        model = Model(s, path=None, author="t")
        for situation, outcome in _levels()[:20]:
            model.record(situation, outcome)
        held = _levels()[150:]
        return sum(model.probabilities(d).get(o, 0.0) for d, o in held) / len(held)

    assert (1 - sure(spec)) * 10 < 1 - sure(old)  # the wrong outcome's share, a tenth of what it was or less


TIMED = {
    "name": "timed",
    "seed": 5,
    "dimension": 1024,
    "temporal_source": "c.t.at",
    "layers": [
        {
            "name": "c",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "kind"},
                        {"name": "size", "numeric_config": {"min_value": 0, "max_value": 100, "bin_width": 1}},
                    ],
                },
                {"name": "t", "roles": [{"name": "at", "similarity_weight": 0}]},
            ],
        }
    ],
}


def _drift(model: Model, start: float, step: float) -> None:
    """Kind a meant 'old' for the first 200 cases and 'new' for the last 100; kind b always 'b'. Sizes vary, so
    a case's nearest precedents are old and new alike, two old to one new."""
    rng = random.Random(8)
    for i in range(300):
        kind = "a" if i % 2 == 0 else "b"
        outcome = "b" if kind == "b" else ("old" if i < 200 else "new")
        data = {"c": {"s": {"kind": kind, "size": rng.randrange(100)}, "t": {"at": start + i * step}}}
        model.record(data, outcome)


def test_calibrate_fits_a_half_life_where_answers_drift_and_keeps_it_with_the_store(tmp_path) -> None:
    day, start = kernel.DAY, 1_700_000_000.0
    path = str(tmp_path / "t.sqlite")
    model = Model(Spec.from_json(TIMED), path=path, author="t")
    _drift(model, start, day)
    model.calibrate(sample=80)
    half = model.space.half_life()
    assert half is not None and half < 300 * day
    late = {"c": {"s": {"kind": "a", "size": 50}, "t": {"at": start + 300 * day}}}
    assert model.decide(late)["outcome"] == "new"  # the newer precedents outvote the older majority
    model.space.close()
    again = Model(Spec.from_json(TIMED), path=path, author="t")
    assert again.space.half_life() == half and again.decide(late)["outcome"] == "new"
    off = again.configure(recency=False)
    assert off["recency"] is False and again.decide(late)["outcome"] == "old"  # time off: the majority, as before
    again.space.close()


def test_no_half_life_where_the_store_spans_no_time_or_time_does_not_help() -> None:
    quick = Model(Spec.from_json(TIMED), path=None, author="t")
    _drift(quick, 1_700_000_000.0, 1.0)  # 200 cases in 200 seconds: no time to weigh
    quick.calibrate(sample=80)
    assert quick.space.half_life() is None
    steady = Model(Spec.from_json(LEVELS), path=None, author="t")
    for i, (situation, outcome) in enumerate(_levels()):
        steady.space.record(steady.spec.situation(situation), outcome, ts=1_700_000_000.0 + i * kernel.DAY)
    steady.calibrate(sample=80)
    assert steady.space.half_life() is None  # no drift: no half-life beats none
