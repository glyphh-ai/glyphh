"""The kernel's invariants, as tests."""

import numpy as np
import pytest

from glyphh_kernel import (ENCODING, Space, Strand, bind, bundle, roll, sim,
                           symbol)


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
    """The nearest row clears the bar; distant rows must not vote.
    3 of 4 shared attributes measure ~0.44 under the unbiased
    tie-break, so the bar for 'same kind of situation' is 0.4."""
    space = Space(min_sim=0.4)
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


@pytest.mark.sqlite_only
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


@pytest.mark.sqlite_only
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


# ── encoding 2: unbiased tie-breaks, time, events, many answers ─────

def test_tiebreak_has_no_position_bias():
    """Which attribute differs must not change similarity. Encoding 1
    derived tie-breaks from the first sorted part: differing in the
    first attribute cost ~2x more than differing in the last."""
    space = Space()
    for n in (2, 4, 6):
        base = {f"a{i}": f"v{i}" for i in range(n)}
        first, last = dict(base), dict(base)
        first["a0"] = "X"
        last[f"a{n - 1}"] = "X"
        g = space.encode(base)
        gap = abs(sim(g, space.encode(first)) - sim(g, space.encode(last)))
        assert gap < 0.06, f"n={n}: position bias {gap:.3f}"


def test_bundle_is_order_free():
    parts = [symbol(k) for k in ("a", "b", "c", "d")]
    assert np.array_equal(bundle(parts), bundle(parts[::-1]))


@pytest.mark.sqlite_only
def test_old_encoding_store_reencodes_on_open(tmp_path):
    """A populated file with no encoding stamp predates encoding 2:
    opening it re-encodes the glyphs so fresh queries still match."""
    import sqlite3
    path = str(tmp_path / "v1.db")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE precedents (id TEXT PRIMARY KEY,"
               " situation TEXT NOT NULL, outcome TEXT NOT NULL,"
               " dim INTEGER NOT NULL, glyph BLOB NOT NULL,"
               " author TEXT NOT NULL DEFAULT 'anon')")
    stale = np.ones(4096, dtype=np.int8)       # an encoding-1 glyph, say
    db.execute("INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
               ("r1", '{"task": "x", "constraint": "y"}', "out", 4096,
                stale.tobytes(), "a"))
    db.commit(); db.close()
    space = Space(path=path)
    answer = space.query({"task": "x", "constraint": "y"})
    assert answer.top == "out" and answer.receipts[0][1] > 0.99
    space.close()
    db = sqlite3.connect(path)
    assert db.execute("SELECT value FROM meta WHERE key='encoding'"
                      ).fetchone()[0] == str(ENCODING)
    assert db.execute("SELECT ts FROM precedents").fetchone()[0] == 0.0
    db.close()


@pytest.mark.sqlite_only
def test_events_persist_so_reencoding_is_lossless(tmp_path):
    from glyphh_kernel import reencode_store
    import sqlite3
    path = str(tmp_path / "ev.db")
    events = [symbol("up"), symbol("down")]
    with Space(path=path) as space:
        space.record({"kind": "flap"}, "scale_down", events=events)
    db = sqlite3.connect(path)
    db.execute("UPDATE precedents SET glyph = ?",
               (np.ones(4096, dtype=np.int8).tobytes(),))
    db.commit(); db.close()
    assert reencode_store(path) == 1
    with Space(path=path) as space:
        answer = space.query({"kind": "flap"}, events=events)
        assert answer.receipts[0][1] > 0.99   # trajectory survived


def test_records_are_time_stamped(tmp_path):
    path = str(tmp_path / "t.db")
    with Space(path=path) as space:
        space.record({"k": "v"}, "a", ts=100.0)
        space.record({"k": "v"}, "a", ts=200.0)
    with Space(path=path) as space:
        assert space.evidence({"k": "v"}, "a").latest == 200.0


def test_answers_reads_many_true_outcomes():
    """A file that imports three modules is not a disagreement: each
    outcome is gated on its own count, not its share of the vote."""
    space = Space(min_sim=0.4)
    situation = {"file": "app.py", "relation": "imports"}
    for module in ("os", "json", "numpy"):
        for grader in ("a", "b", "c"):
            space.author = grader
            space.record(situation, module)
    answer = space.query(situation)
    assert answer.confidence < 0.5            # the vote splits three ways
    got = space.answers(situation, min_count=3)
    assert sorted(e.outcome for e in got) == ["json", "numpy", "os"]
    assert all(e.count == 3 and e.authors == ["a", "b", "c"] for e in got)
    assert space.answers({"file": "other.py", "relation": "x"}) == []


def test_evidence_sees_past_top_k():
    space = Space(k=3)
    situation = {"k": "v"}
    for _ in range(5):
        space.record(situation, "crowd")
    space.record({"k": "v", "near": "miss"}, "rare")         # close, not top
    assert "rare" not in space.query(situation).outcomes   # crowded out
    assert space.evidence(situation, "rare").count == 1


# ── decide(): the contract, with the newest evidence winning ────────

def _stores(n_wins=3, t0=10.0):
    wins, vetoes = Space(min_sim=0.4), Space(min_sim=0.4)
    for i in range(n_wins):
        wins.record({"task": "deploy", "env": "prod"}, "canary", ts=t0 + i)
    return wins, vetoes


def test_decide_reflex_needs_three_gates():
    from glyphh_kernel import decide
    wins, vetoes = _stores(3)
    d = decide(wins, vetoes, {"task": "deploy", "env": "prod"})
    assert d.act and d.reason == "reflex" and d.outcome == "canary"
    one, _ = _stores(1)
    assert decide(one, vetoes, {"task": "deploy", "env": "prod"}
                  ).reason == "uncalibrated"
    assert decide(wins, vetoes, {"task": "cook", "env": "home"}
                  ).reason == "insufficient"


def test_decide_newer_veto_blocks_newer_win_lifts():
    from glyphh_kernel import decide
    situation = {"task": "deploy", "env": "prod"}
    wins, vetoes = _stores(3)                   # wins at t=10..12
    vetoes.record(situation, "canary", ts=20.0)  # the world changed
    d = decide(wins, vetoes, situation)
    assert not d.act and d.reason == "vetoed"
    wins.record(situation, "canary", ts=30.0)    # reproduced again later
    d = decide(wins, vetoes, situation)
    assert d.act and d.lifted and d.reason == "reflex"
    vetoes.record(situation, "canary", ts=40.0)  # and it failed again
    assert decide(wins, vetoes, situation).reason == "vetoed"


def test_decide_min_veto_count_resists_a_lone_saboteur():
    from glyphh_kernel import decide
    situation = {"task": "deploy", "env": "prod"}
    wins, vetoes = _stores(3)
    vetoes.author = "newcomer"
    vetoes.record(situation, "canary", ts=20.0)
    assert decide(wins, vetoes, situation).reason == "vetoed"   # fail-closed
    assert decide(wins, vetoes, situation, min_veto_count=2).act
    vetoes.author = "second"
    vetoes.record(situation, "canary", ts=21.0)
    assert decide(wins, vetoes, situation,
                  min_veto_count=2).reason == "vetoed"


def test_decide_legacy_rows_stay_fail_closed():
    """Rows from before time-stamping carry ts=0: a legacy veto still
    blocks legacy wins, exactly as encoding 1 behaved."""
    from glyphh_kernel import decide
    situation = {"task": "deploy", "env": "prod"}
    wins, vetoes = _stores(3, t0=0.0)
    wins._ts = [0.0] * len(wins._ts)
    vetoes.record(situation, "canary", ts=0.0)
    assert decide(wins, vetoes, situation).reason == "vetoed"


def test_decision_serializes():
    from glyphh_kernel import decide
    wins, vetoes = _stores(3)
    out = decide(wins, vetoes, {"task": "deploy", "env": "prod"}).to_json()
    assert out["act"] is True and out["answer"]["count"] == 3


# ── encoding 3: data, weights at every level, fact trees ────────────

from glyphh_kernel import encode, explain  # noqa: E402

DECIDES = {"goal": 1.0, "risk": 1.0, "team": 0.1, "region": 0}
QUERY = {"goal": "move_data", "risk": "downtime", "team": "infra",
         "region": "eu"}
DECISIVE = {"goal": "move_data", "risk": "downtime", "team": "platform",
            "region": "us"}
INCIDENTAL = {"goal": "other", "risk": "lock_table", "team": "infra",
              "region": "eu"}


def test_weighted_bundle_is_order_free_and_unit_weights_change_nothing():
    a, b, c, d = (symbol(k) for k in "abcd")
    for parts in ([a, b], [a, b, c], [a, b, c, d], [a, a, b, b]):
        assert np.array_equal(bundle(parts), bundle(parts, [1] * len(parts)))
        assert np.array_equal(bundle(parts, [3.0] * len(parts)),
                              bundle(parts[::-1], [3.0] * len(parts)))
    w = [0.2, 1.0, 0.7, 0.5]
    assert np.array_equal(bundle([a, b, c, d], w),
                          bundle([d, c, b, a], w[::-1]))


def test_weight_is_a_voice_in_the_vote():
    a, b, c = (symbol(k) for k in "abc")
    heavy = bundle([a, b, c], [3.0, 1.0, 1.0])
    assert sim(heavy, a) > 0.9 > sim(heavy, b)
    assert np.array_equal(bundle([a, b], [1.0, 0.0]), a)  # 0 drops a part
    with pytest.raises(ValueError):
        bundle([a, b], [0, 0])
    with pytest.raises(ValueError):
        bundle([a, b], [1.0, -1.0])
    with pytest.raises(ValueError):
        bundle([a, b], [1.0])


def test_flat_situation_encodes_as_it_always_has():
    s = {"task": "deploy", "env": "prod"}
    old = bundle([bind(symbol("attr:env"), symbol("val:prod")),
                  bind(symbol("attr:task"), symbol("val:deploy"))])
    assert np.array_equal(encode(s), old)
    assert np.array_equal(Space().encode(s), old)


def test_nested_data_keeps_paths_apart():
    assert abs(sim(encode({"a": {"b": "x"}}), encode({"b": {"a": "x"}}))) < 0.06
    assert sim(encode({"plan": {"step": "a", "owner": "x"}}),
               encode({"plan": {"step": "a", "owner": "y"}})) > 0.2
    # arrays are sets; scalars are typed text
    assert np.array_equal(encode({"t": ["a", "b"]}), encode({"t": ["b", "a"]}))
    assert abs(sim(encode({"n": 3}), encode({"n": "3"})) - 1.0) < 1e-9
    assert abs(sim(encode({"n": True}), encode({"n": "True"}))) < 0.06
    for empty in ({}, {"a": {}}, {"a": []}):
        with pytest.raises(ValueError):
            encode(empty)


def test_weights_decide_which_neighbor_is_near():
    # unweighted, sharing two incidental attributes looks as close as
    # sharing the two that decide; weights say which ones matter
    assert abs(sim(encode(QUERY), encode(DECISIVE))
               - sim(encode(QUERY), encode(INCIDENTAL))) < 0.05
    assert sim(encode(QUERY, DECIDES), encode(DECISIVE)) > \
        sim(encode(QUERY, DECIDES), encode(INCIDENTAL)) + 0.1


def test_fact_tree_adds_up_and_cites_every_key():
    root = explain(QUERY, DECISIVE, DECIDES)
    assert {c.key for c in root.children} == set(QUERY)
    assert abs(sum(c.share for c in root.children) - root.score) < 1e-12
    assert root.score > 0.9
    assert explain(QUERY, INCIDENTAL, DECIDES).score < 0.1
    by = {c.key: c for c in root.children}
    assert by["risk"].score == pytest.approx(1.0) and by["region"].weight == 0


def test_fact_tree_nests_and_reports_one_sided_keys():
    q = {"plan": {"step": "dual_write", "owner": "ana"}, "risk": "downtime"}
    r = {"plan": {"step": "dual_write", "owner": "bo"}, "risk": "downtime",
         "extra": [1, 2]}
    root = explain(q, r, {"plan": {"*": 2, "owner": 0}, "extra": 0})
    assert root.score == pytest.approx(1.0)
    by = {c.key: c for c in root.children}
    assert by["extra"].status == "record_only" and by["extra"].score == 0
    assert by["plan"].weight == 2 and len(by["plan"].children) == 2
    # unweighted, the one-sided key and the differing owner both cost
    assert explain(q, r).score < 0.7
    doc = root.to_json()
    assert doc["children"][0]["key"] == "extra" and "record" in doc["children"][0]
    assert "extra: not in the query" in root.to_text()


def test_space_reads_take_weights_and_facts_explain_them(tmp_path):
    path = str(tmp_path / "w.db")
    space = Space(min_sim=0.2, path=path)
    for _ in range(3):
        space.record(DECISIVE, "dual_write")
        space.record(INCIDENTAL, "batch_copy")
    assert space.query(QUERY, weights=DECIDES).top == "dual_write"
    assert space.matches(QUERY, "dual_write", weights=DECIDES) > \
        space.matches(QUERY, "batch_copy", weights=DECIDES)
    facts = space.facts(QUERY, weights=DECIDES)
    assert len(facts) == 6 and facts[0].outcome == "dual_write"
    assert facts[0].score > 0.9 > 0.1 > facts[-1].score
    assert facts[0].to_json()["tree"]["children"]
    space.close()
    # situations come back from the file, nested ones too
    nested = {"plan": {"step": "x"}, "risk": "y"}
    Space(path=path).record(nested, "z")
    again = Space(path=path)
    top = again.facts(nested, top=1)[0]
    assert top.outcome == "z" and top.score == pytest.approx(1.0)


def test_weights_can_raise_a_match_over_the_bar():
    # a perfect match on the keys that decide clears a bar the glyph,
    # diluted by incidental keys, cannot
    space = Space(min_sim=0.4)
    space.record(DECISIVE, "dual_write")
    assert not space.query(QUERY).sufficient
    weighted = space.query(QUERY, weights=DECIDES)
    assert weighted.sufficient and weighted.support > 0.9
    assert space.facts(QUERY, weights=DECIDES, min_score=0.99) == []


def test_events_are_one_more_key_in_the_tree():
    up, down = symbol("up"), symbol("down")
    space = Space()
    space.record({"task": "t"}, "same", events=[up, down])
    space.record({"task": "t"}, "flipped", events=[down, up])
    space.record({"task": "t"}, "none")
    facts = space.facts({"task": "t"}, events=[up, down])
    assert [f.outcome for f in facts][0] == "same"
    by = {f.outcome: {c.key: c for c in f.root.children} for f in facts}
    assert by["same"]["~events"].score == pytest.approx(1.0)
    assert by["none"]["~events"].status == "query_only"
    assert by["flipped"]["~events"].score < 0.7


# ── calibrated probability on the fact tree ─────────────────────────

def _routed_space(path=None):
    space = Space(path=path)
    rng = np.random.default_rng(7)
    for i in range(60):
        team = ["node", "net", "storage"][i % 3]
        noise = f"n{rng.integers(0, 5)}"
        space.record({"component": team, "noise": noise}, f"sig/{team}",
                     ts=float(i))
    return space


def test_probabilities_sum_to_one_and_follow_the_evidence():
    space = _routed_space()
    p = space.probabilities({"component": "node", "noise": "n9"},
                            weights={"noise": 0})
    assert abs(sum(p.values()) - 1.0) < 1e-12
    assert max(p, key=p.get) == "sig/node" and p["sig/node"] > 0.9
    facts = space.facts({"component": "node", "noise": "n9"},
                        weights={"noise": 0}, top=3)
    assert facts[0].probability == pytest.approx(p["sig/node"])
    assert facts[0].to_json()["probability"] == round(p["sig/node"], 4)
    assert facts[0].to_text().startswith("sig/node  p ")


def test_calibrate_fits_tau_and_the_file_keeps_it(tmp_path):
    path = str(tmp_path / "c.db")
    space = _routed_space(path)
    tau = space.calibrate(sample=30, weights={"noise": 0})
    assert tau in (0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5, 1.0)
    space.close()
    assert Space(path=path).tau == tau
    assert Space(path=path, tau=0.5).tau == 0.5   # given wins
    with pytest.raises(ValueError):
        Space().calibrate()


# ── named outputs: one store, one record per case, many answers ─────


def _two_output_space(path=None):
    """Each case: its component decides `team`; its severity decides `page`."""
    space = Space(path=path)
    for i in range(60):
        team = ["node", "net", "storage"][i % 3]
        sev = ["low", "high"][i % 2]
        space.record({"component": team, "sev": sev}, rid=f"c{i}", ts=float(i),
                     outcomes={"team": f"sig/{team}",
                               "page": "yes" if sev == "high" else "no"})
    return space


def test_one_record_answers_every_output():
    space = _two_output_space()
    case = {"component": "net", "sev": "high"}
    assert space.outputs() == ["page", "team"]       # no default outcome given
    assert space.query(case, output="team").top == "sig/net"
    assert space.query(case, output="page").top == "yes"
    assert space.query(case).top is None              # the default output: ungraded
    assert space.probabilities(case) == {}
    p = space.probabilities(case, weights={"component": 2.0}, output="team")
    assert max(p, key=p.get) == "sig/net"
    assert space.evidence(case, "yes", output="page").count > 0
    assert space.evidence(case, "yes").count == 0
    assert [e.outcome for e in space.answers(case, output="page")][0] == "yes"
    assert space.matches(case, "no", output="page") > 0
    assert space.matches(case, "no", output="ghost") == 0.0
    facts = space.facts(case, top=2, output="team")
    assert facts[0].outcome == "sig/net" and facts[0].probability > 0
    assert space.facts(case, top=1)[0].outcome is None
    assert len(space.graded("page")) == 60 and space.graded() == []


def test_the_default_output_is_the_outcome_by_either_name():
    space = Space()
    space.record({"a": 1}, "x", outcomes={"default": "x", "o": "y"})
    space.record({"a": 2}, outcomes={"default": "z"})
    assert space.graded() == [({"a": 1}, "x"), ({"a": 2}, "z")]
    assert space.outputs() == ["default", "o"]
    with pytest.raises(ValueError, match="same output"):
        space.record({"a": 3}, "x", outcomes={"default": "w"})


@pytest.mark.parametrize("outcomes, said", [
    (["x"], "object"),
    ({"o": ""}, "non-empty"),
    ({"o": 3}, "non-empty"),
    ({"bad name": "x"}, "letters"),
    ({"9lives": "x"}, "letters"),
])
def test_named_outcomes_are_checked(outcomes, said):
    with pytest.raises(ValueError, match=said):
        Space().record({"a": 1}, outcomes=outcomes)


def test_an_output_name_is_checked_on_every_read():
    space = _two_output_space()
    for read in (lambda: space.query({"a": 1}, output="x y"),
                 lambda: space.graded(output=""),
                 lambda: space.probabilities({"a": 1}, output=7)):
        with pytest.raises(ValueError, match="letters"):
            read()


def test_grade_adds_replaces_and_takes_away_an_answer(tmp_path):
    path = str(tmp_path / "g.db")
    space = Space(path=path)
    rid = space.record({"a": 1}, outcomes={"o": "x"})
    space.grade(rid, "o", "y")
    space.grade(rid, "p", "z")
    space.grade(rid, None, "d")                       # the default output
    assert [space.graded(o) for o in ("o", "p", None)] == [
        [({"a": 1}, "y")], [({"a": 1}, "z")], [({"a": 1}, "d")]]
    space.grade(rid, "p", None)
    space.grade(rid, "default", None)
    assert space.graded("p") == [] and space.graded() == []
    space.close()
    again = Space(path=path)
    assert again.graded("o") == [({"a": 1}, "y")]
    assert again.graded("p") == [] and again.graded() == []
    with pytest.raises(KeyError):
        again.grade("nobody", "o", "x")
    with pytest.raises(ValueError, match="non-empty"):
        again.grade(rid, "o", "")
    memory = Space()
    mid = memory.record({"a": 1}, "x", outcomes={"o": "y"})
    memory.grade(mid, "o", None)
    memory.grade(mid, "o", "w")
    memory.grade(mid, None, None)
    assert memory.graded("o") == [({"a": 1}, "w")] and memory.graded() == []


def test_recording_an_id_again_replaces_every_answer(tmp_path):
    path = str(tmp_path / "r.db")
    space = Space(path=path)
    space.record({"a": 1}, rid="c", outcomes={"o": "x", "p": "y"})
    space.record({"a": 2}, rid="c", outcomes={"o": "z"})
    assert space.graded("o") == [({"a": 2}, "z")] and space.graded("p") == []
    space.close()
    assert Space(path=path).graded("p") == []


def test_each_output_calibrates_its_own_tau_and_the_file_keeps_them(tmp_path):
    path = str(tmp_path / "t.db")
    space = _two_output_space(path)
    team = space.calibrate(sample=30, output="team")
    page = space.calibrate(sample=30, output="page")
    assert space.tau == 0.12                          # the default's untouched
    assert space._tau_for("team") == team and space._tau_for("page") == page
    assert space._tau_for("ghost") == 0.12
    with pytest.raises(ValueError, match="at least 10"):
        space.calibrate(output="ghost")
    space.close()
    for again in (Space(path=path), Space(path=path, readonly=True)):
        assert again._tau_for("team") == team and again._tau_for("page") == page
        assert again.outputs() == ["page", "team"]
    given = Space(path=path, tau=0.5)
    assert given._tau_for("team") == 0.5               # given wins
    memory = _two_output_space()
    assert memory.calibrate(sample=30, output="page") == page


def test_another_writers_answers_arrive_on_refresh(tmp_path):
    path = str(tmp_path / "w.db")
    a, b = Space(path=path), Space(path=path)
    rid = a.record({"a": 1}, outcomes={"o": "x"})
    b.refresh()
    assert b.graded("o") == [({"a": 1}, "x")]
    a.grade(rid, "o", "y")
    b.refresh()
    assert b.graded("o") == [({"a": 1}, "y")]


def test_merge_brings_every_answer_with_the_precedent(tmp_path):
    src, dst = str(tmp_path / "s.db"), str(tmp_path / "d.db")
    s = Space(path=src)
    s.record({"a": 1}, "x", rid="c1", outcomes={"o": "y"})
    s.close()
    d = Space(path=dst)
    assert d.merge(src) == 1 and d.merge(src) == 0
    assert d.graded("o") == [({"a": 1}, "y")] and d.graded() == [({"a": 1}, "x")]
    d.close()
    assert Space(path=dst).graded("o") == [({"a": 1}, "y")]
    memory = Space()
    assert memory.merge(src) == 1 and memory.graded("o") == [({"a": 1}, "y")]


@pytest.mark.sqlite_only
def test_a_file_from_before_named_outputs_still_opens(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    s = Space(path=path)
    s.record({"a": 1}, "x")
    s.close()
    db = sqlite3.connect(path)
    db.execute("DROP TABLE outcomes")
    db.commit()
    db.close()
    ro = Space(path=path, readonly=True)
    assert ro.graded() == [({"a": 1}, "x")] and ro.outputs() == ["default"]
    other = Space(path=str(tmp_path / "new.db"))
    assert other.merge(path) == 1 and other.outputs() == ["default"]
