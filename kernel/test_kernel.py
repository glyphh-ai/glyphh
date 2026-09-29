"""The kernel's invariants, as tests."""

import numpy as np
import pytest

from glyphh_kernel import Space, Strand, bind, bundle, roll, sim, symbol


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
    assert answer.receipts and all(len(r) == 5 for r in answer.receipts)


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


def test_below_min_sim_rows_carry_no_vote():
    """The nearest row clears the bar; distant rows must not vote."""
    space = Space(min_sim=0.5)
    space.record({"a": "1", "b": "2", "c": "3", "d": "4"}, "right")
    for i in range(5):
        space.record({"w": f"x{i}", "y": f"z{i}"}, "wrong")
    answer = space.query({"a": "1", "b": "2", "c": "3", "d": "9"})
    assert answer.top == "right"
    assert answer.count == 1
    assert "wrong" not in answer.outcomes


def test_matches_is_undilutable():
    """One failure of the exact action is visible however many
    unrelated failures surround it."""
    vetoes = Space()
    situation = {"kind": "db", "sev": "high"}
    vetoes.record(situation, "restart")
    for i in range(20):
        vetoes.record({"kind": f"other{i}"}, "scale_up")
    assert vetoes.matches(situation, "restart") > 0.9
    assert vetoes.matches(situation, "failover") == 0.0
    assert Space().matches(situation, "restart") == 0.0


def test_count_exposes_sparse_consensus():
    space = Space()
    space.record({"k": "v"}, "out")
    answer = space.query({"k": "v"})
    assert answer.confidence == 1.0 and answer.count == 1  # consensus of one


def test_close_and_context_manager(tmp_path):
    path = str(tmp_path / "wins.db")
    with Space(path=path) as space:
        space.record({"k": "v"}, "out")
    reopened = Space(path=path)
    assert len(reopened) == 1
    reopened.close()


def test_space_decay_configurable():
    events = [symbol("a"), symbol("b"), symbol("c")]
    fast = Space(decay=0.2).encode({"k": "v"}, events=events)
    slow = Space(decay=0.9).encode({"k": "v"}, events=events)
    assert not np.array_equal(fast, slow)


def test_bundle_tiebreak_unbiased_at_any_dim():
    a = symbol("a", dim=1000)
    b = symbol("b", dim=1000)
    out = bundle([a, b])
    assert abs(int(out.sum())) < 200, "tie-break must not bias toward +1"
    assert np.array_equal(out, bundle([a, b]))  # and stay deterministic


def test_authorship_carried_in_receipts(tmp_path):
    path = str(tmp_path / "shared.db")
    a = Space(author="agent-a", path=path)
    a.record({"k": "v"}, "out")
    a.close()
    b = Space(author="agent-b", path=path)
    b.record({"k": "v"}, "out")
    receipt_authors = {r[4] for r in b.query({"k": "v"}).receipts}
    assert receipt_authors == {"agent-a", "agent-b"}
    b.close()


def test_refresh_sees_other_writers(tmp_path):
    path = str(tmp_path / "shared.db")
    a = Space(author="agent-a", path=path)
    b = Space(author="agent-b", path=path)
    a.record({"k": "v"}, "out")
    assert not b.query({"k": "v"}).sufficient
    assert b.refresh() == 1
    assert b.query({"k": "v"}).top == "out"
    a.close(); b.close()


def test_merge_unions_by_id(tmp_path):
    pa, pb = str(tmp_path / "a.db"), str(tmp_path / "b.db")
    a = Space(author="agent-a", path=pa)
    shared_id = a.record({"k": "v"}, "out")
    a.close()
    b = Space(author="agent-b", path=pb)
    b.record({"k": "v"}, "out", rid=shared_id)  # same id: no duplicate
    b.record({"x": "y"}, "other")
    b.close()
    a2 = Space(author="agent-a", path=pa)
    assert a2.merge(pb) == 1                    # only the new one
    assert len(a2) == 2
    assert a2.query({"x": "y"}).receipts[0][4] == "agent-b"
    a2.close()
    a3 = Space(path=pa)                          # merge persisted
    assert len(a3) == 2
    a3.close()


def test_pre_author_file_migrates(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE precedents (id TEXT PRIMARY KEY,"
               " situation TEXT NOT NULL, outcome TEXT NOT NULL,"
               " dim INTEGER NOT NULL, glyph BLOB NOT NULL)")
    glyph = Space().encode({"k": "v"})
    db.execute("INSERT INTO precedents VALUES (?, ?, ?, ?, ?)",
               ("old-row", "{}", "out", 4096, glyph.tobytes()))
    db.commit(); db.close()
    space = Space(path=path)
    assert space.query({"k": "v"}).receipts[0][4] == "anon"
    space.close()


def test_kernel_carries_its_own_spec():
    from glyphh_kernel import SPEC, spec
    assert spec() == SPEC
    for anchor in ("NOTHING UNGRADED", "three gates", "matches()",
                   "Attribute hygiene", "merge("):
        assert anchor in SPEC, f"spec lost its guidance on: {anchor}"


def test_small_situations_not_correlated_by_tiebreak():
    """Two-attribute situations with NO shared attributes must sit
    near zero similarity. A shared global tie-break vector used to
    inject a common component into every even-count bundle."""
    space = Space()
    a = space.encode({"person": "chris", "topic": "fishing"}).astype(float)
    b = space.encode({"person": "dana", "topic": "sailing"}).astype(float)
    c = space.encode({"kind": "deploy", "env": "prod"}).astype(float)
    assert abs(float(a @ b) / len(a)) < 0.08
    assert abs(float(a @ c) / len(a)) < 0.08


def test_reencode_store_restores_matching(tmp_path):
    from glyphh_kernel import reencode_store
    import sqlite3
    path = str(tmp_path / "wins.db")
    with Space(path=path) as space:
        space.record({"person": "chris", "topic": "fishing"}, "gold_spoon")
    # simulate a stale encoding: corrupt the stored glyph
    db = sqlite3.connect(path)
    stale = np.zeros(4096, dtype=np.int8)
    db.execute("UPDATE precedents SET glyph = ?", (stale.tobytes(),))
    db.commit(); db.close()
    broken = Space(path=path)
    assert not broken.query({"person": "chris", "topic": "fishing"}).sufficient
    broken.close()
    assert reencode_store(path) == 1
    fixed = Space(path=path)
    answer = fixed.query({"person": "chris", "topic": "fishing"})
    assert answer.sufficient and answer.top == "gold_spoon"
    assert answer.receipts[0][1] > 0.99
    fixed.close()
