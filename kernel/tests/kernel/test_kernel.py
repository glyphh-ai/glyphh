"""The kernel's invariants, as tests. The kernel is a single file with
no dependencies on the rest of this repo — these tests import it the
way a stranger would."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kernel"))

from glyphh_kernel import Space, Strand, bind, bundle, roll, sim, symbol  # noqa: E402


def test_bind_self_inverse():
    a, b = symbol("a"), symbol("b")
    assert np.array_equal(bind(bind(a, b), b), a)


def test_symbols_deterministic_and_seed_scoped():
    assert np.array_equal(symbol("k", 7), symbol("k", 7))
    assert not np.array_equal(symbol("k", 7), symbol("k", 8))
    assert abs(sim(symbol("a"), symbol("b"))) < 0.06


def test_bundle_resembles_parts():
    a, b = symbol("a"), symbol("b")
    assert sim(bundle([a, b]), a) > 0.4


def test_roll_orthogonal_and_invertible():
    a = symbol("a")
    assert np.array_equal(roll(roll(a, 3), -3), a)
    assert abs(sim(roll(a, 1), a)) < 0.06


def test_strand_order_matters():
    s1 = Strand([symbol("x"), symbol("y")])
    s2 = Strand([symbol("y"), symbol("x")])
    assert sim(s1.state(), s2.state()) < 0.7


def test_space_answers_with_receipts():
    space = Space()
    space.record({"kind": "db", "sev": "high"}, "failover")
    space.record({"kind": "db", "sev": "high"}, "failover")
    space.record({"kind": "spike"}, "scale_up")
    answer = space.query({"kind": "db", "sev": "high"})
    assert answer.sufficient and answer.top == "failover"
    assert answer.receipts and all(len(r) == 4 for r in answer.receipts)


def test_empty_space_is_insufficient():
    assert not Space().query({"kind": "db"}).sufficient


def test_events_disambiguate_by_order():
    e1 = [symbol("up"), symbol("down")]
    e2 = [symbol("down"), symbol("up")]
    space = Space()
    space.record({"kind": "flap"}, "scale_down", events=e1)
    space.record({"kind": "flap"}, "scale_up", events=e2)
    assert space.query({"kind": "flap"}, events=e1).top == "scale_down"
    assert space.query({"kind": "flap"}, events=e2).top == "scale_up"


def test_persistence_round_trip(tmp_path):
    path = str(tmp_path / "wins.db")
    first = Space(path=path)
    first.record({"k": "v"}, "out")
    second = Space(path=path)
    assert len(second) == 1
    assert second.query({"k": "v"}).top == "out"


def test_dimension_mismatch_refused(tmp_path):
    path = str(tmp_path / "wins.db")
    Space(dim=2048, path=path).record({"k": "v"}, "out")
    with pytest.raises(ValueError):
        Space(dim=4096, path=path)
