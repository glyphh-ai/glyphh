"""Tests for DecisionSpace SQLite persistence and the default store."""

import numpy as np
import pytest

import glyphh.decision.store as store
from glyphh.decision import DecisionSpace

DIM = 1024


def test_decisions_survive_restart(tmp_path):
    db = str(tmp_path / "decisions.db")
    space = DecisionSpace(dimension=DIM, persist_path=db)
    space.record({"amount": "small"}, "approved", facts={"case": "a"})
    space.record({"amount": "large"}, "declined")

    reopened = DecisionSpace(dimension=DIM, persist_path=db)
    assert len(reopened) == 2
    answer = reopened.query({"amount": "small"})
    assert answer.top_outcome == "approved"
    # glyphs restored bit-exactly
    assert np.array_equal(space._decisions[0].glyph,
                          reopened._decisions[0].glyph)
    assert reopened._decisions[0].facts == {"case": "a"}


def test_dimension_mismatch_refuses_to_load(tmp_path):
    db = str(tmp_path / "decisions.db")
    DecisionSpace(dimension=DIM, persist_path=db).record({"a": "b"}, "x")
    with pytest.raises(ValueError):
        DecisionSpace(dimension=DIM * 2, persist_path=db)


def test_default_store_singleton(tmp_path, monkeypatch):
    monkeypatch.setenv("GLYPHH_DECISIONS_DB", str(tmp_path / "d.db"))
    store.reset_default_space()
    a = store.get_default_space(dimension=DIM)
    b = store.get_default_space()
    assert a is b
    a.record({"k": "v"}, "done")
    store.reset_default_space()
    assert len(store.get_default_space(dimension=DIM)) == 1
    store.reset_default_space()
