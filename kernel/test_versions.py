"""The release says the same everywhere (CHANGELOG.md, the rule), and 3.13.0's one answer-changing change."""

from __future__ import annotations

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
