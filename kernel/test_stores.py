"""Kernel 3.12: the storage interface (SqliteStore, PostgresStore, shortlist reads) and the fixes a worker serving
many models needs (per-model lexicon, a bounded symbol cache, forget, record_many, ask_below). Tests marked
postgres run with GLYPHH_TEST_POSTGRES set (a Postgres with pgvector); the rest everywhere."""

from __future__ import annotations

import json
import os
import random
import uuid

import numpy as np
import pytest

import glyphh_kernel as kernel
from glyphh_kernel import ReadOnlyError, Space, SqliteStore, Store
from glyphh_spec import Model, Spec, SpecError

POSTGRES = os.environ.get("GLYPHH_TEST_POSTGRES")

TEXT = {
    "name": "t",
    "seed": 3,
    "dimension": 2048,
    "layers": [{"name": "m", "segments": [{"name": "b", "roles": [{"name": "text", "text_encoding": "bag_of_words"}, {"name": "id", "key_part": True, "similarity_weight": 0}]}]}],
}
CASES = {
    "name": "c",
    "seed": 5,
    "dimension": 2048,
    "layers": [
        {
            "name": "a",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "color"},
                        {"name": "shape"},
                        {"name": "size", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
}


def text_cases(n: int = 120, seed: int = 1) -> list[tuple[dict, str]]:
    rng = random.Random(seed)
    words = {"lost": ["lost", "stolen", "missing"], "fx": ["rate", "exchange", "currency"], "top": ["top", "up", "load"]}
    filler = ["my", "card", "please", "the", "help"]
    out = []
    for i in range(n):
        label = rng.choice(sorted(words))
        text = " ".join(rng.sample(filler, 2) + rng.sample(words[label], 2))
        out.append(({"m": {"b": {"text": text, "id": f"c{i}"}}}, label))
    return out


def shape_cases(n: int, seed: int = 2) -> list[tuple[dict, str]]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        color, shape, size = rng.choice("rgbyk"), rng.choice(["sq", "ci", "tr", "pe"]), rng.randint(0, 10)
        good = (color in "rg") ^ (size > 6) ^ (rng.random() < 0.15)
        out.append(({"a": {"s": {"color": color, "shape": shape, "size": size, "id": f"s{i}"}}}, "good" if good else "bad"))
    return out


# ── step 0: the kernel fixes ─────────────────────────────────────────


def test_the_lexicon_is_each_models_own_not_the_processes() -> None:
    """Two models, one with the lexicon and one without, served one after another by one process: each answers
    as it does alone (3.11 switched glyphh_lexicon.LEXICON for the whole process)."""
    from glyphh_lexicon import LEXICON

    def build(lexicon: bool) -> Model:
        spec = Spec.from_json({**TEXT, "settings": {"lexicon": lexicon}})
        model = Model(spec, k=7, min_sim=0.05)
        for data, outcome in text_cases():
            model.record(data, outcome)
        model.learn()
        return model

    alone_on = [build(True).probabilities({"m": {"b": {"text": t, "id": "q"}}}) for t in ("my card went missing", "what rate")]
    alone_off = [build(False).probabilities({"m": {"b": {"text": t, "id": "q"}}}) for t in ("my card went missing", "what rate")]
    on, off = build(True), build(False)
    assert LEXICON.enabled  # no model touched the process's switch
    for i, t in enumerate(("my card went missing", "what rate")):
        assert off.probabilities({"m": {"b": {"text": t, "id": "q"}}}) == alone_off[i]
        assert on.probabilities({"m": {"b": {"text": t, "id": "q"}}}) == alone_on[i]
    assert on.space.lexicon and not off.space.lexicon
    word = kernel.encode([["arrive", 1.0]], seed=1, dim=4096, lexicon=False)
    assert np.array_equal(word, kernel.symbol("val:arrive", 1, 4096))
    assert not np.array_equal(kernel.encode([["arrive", 1.0]], seed=1, dim=4096), word)


def test_configuring_the_lexicon_reencodes_the_store(tmp_path) -> None:
    path = str(tmp_path / "l.db")
    model = Model(Spec.from_json(TEXT), k=7, min_sim=0.05, path=path)
    for data, outcome in text_cases(60):
        model.record(data, outcome)
    model.learn()
    model.configure(lexicon=False)
    fresh = Model(Spec.from_json({**TEXT, "settings": {"lexicon": False}}), k=7, min_sim=0.05)
    for data, outcome in text_cases(60):
        fresh.record(data, outcome)
    fresh.learn()
    q = {"m": {"b": {"text": "card missing please", "id": "q"}}}
    assert model.probabilities(q) == fresh.probabilities(q)
    model.space.close()
    again = Model(Spec.from_json(TEXT), path=path)  # the setting is kept with the store, and so are the glyphs
    assert not again.space.lexicon and again.probabilities(q) == fresh.probabilities(q)


def test_the_symbol_cache_is_bounded_and_answers_the_same() -> None:
    size = kernel.SYMBOL_CACHE
    kernel.SYMBOL_CACHE = 50
    try:
        first = kernel.symbol("k0", 7, 256)
        for i in range(500):
            kernel.symbol(f"k{i}", 7, 256)
        assert len(kernel._SYMBOLS) <= 50
        assert ("k0", 7, 256) not in kernel._SYMBOLS
        assert np.array_equal(kernel.symbol("k0", 7, 256), first)  # made again, the same
        kernel.symbol("k499", 7, 256)
        assert next(reversed(kernel._SYMBOLS)) == ("k499", 7, 256)  # the most recently used last
    finally:
        kernel.SYMBOL_CACHE = size


def test_forget_deletes_one_case_everywhere(tmp_path) -> None:
    path = str(tmp_path / "f.db")
    space = Space(dim=512, path=path)
    a = space.record({"x": "1"}, "yes", outcomes={"other": "o"})
    b = space.record({"x": "2"}, "no")
    space.forget(a)
    assert space._ids == [b] and space._at == {b: 0} and len(space) == 1
    with pytest.raises(KeyError):
        space.forget(a)
    space.close()
    again = Space(dim=512, path=path)
    assert again._ids == [b] and again._named == [{}]
    again.close()
    with pytest.raises(ReadOnlyError):
        Space(dim=512, path=path, readonly=True).forget(b)
    model = Model(Spec.from_json(CASES), path=str(tmp_path / "m.db"))
    rid = model.record(shape_cases(1)[0][0], "good")
    model.forget(rid)
    assert len(model) == 0


def test_record_many_is_one_write_and_counts_what_it_replaced(tmp_path) -> None:
    path = str(tmp_path / "r.db")
    one = Model(Spec.from_json(CASES), path=str(tmp_path / "one.db"))
    many = Model(Spec.from_json(CASES), path=path)
    cases = shape_cases(50)
    for data, outcome in cases:
        one.record(data, outcome, ts=1.0)
    answer = many.record_many([{"data": d, "outcome": o, "ts": 1.0} for d, o in cases[:30]])
    assert answer["added"] == 30 and answer["replaced"] == 0 and answer["precedents"] == 30
    again = many.record_many([{"data": d, "outcome": o, "ts": 1.0} for d, o in cases[20:]])  # ten held already
    assert again["added"] == 20 and again["replaced"] == 10 and again["precedents"] == 50
    assert again["ids"] == [many.spec.key(many.spec.situation(d)) for d, _ in cases[20:]]
    q = shape_cases(1, seed=9)[0][0]
    assert many.probabilities(q) == one.probabilities(q)
    with pytest.raises(SpecError, match=r"cases\[1\]"):  # one bad case refuses the batch, nothing written
        many.record_many([{"data": cases[0][0], "outcome": "good"}, {"data": {"nope": {}}, "outcome": "bad"}])
    assert len(many) == 50
    many.space.close()
    assert len(Model(Spec.from_json(CASES), path=path)) == 50


def test_record_many_on_a_space_replaces_within_the_batch() -> None:
    space = Space(dim=512)
    ids = space.record_many([{"situation": {"x": "1"}, "outcome": "a", "rid": "r"}, {"situation": {"x": "2"}, "outcome": "b", "rid": "r"}])
    assert ids == ["r", "r"] and space._ids == ["r"] and space._outcomes == ["b"]
    with pytest.raises(ValueError):
        space.record_many([{"situation": {"x": "1"}, "colour": "a"}])


def test_the_id_index_follows_every_drop() -> None:
    space = Space(dim=256)
    for i in range(20):
        space.record({"x": str(i)}, "o", rid=f"r{i}")
    for rid in ("r3", "r0", "r19", "r10"):
        space.forget(rid)
    space.record({"x": "again"}, "o", rid="r5")  # a replace moves it to the end
    assert space._at == {rid: i for i, rid in enumerate(space._ids)} and space._ids[-1] == "r5"


def test_ask_below_asks_under_a_confidence_bar() -> None:
    spec = Spec.from_json({**CASES, "output": {"ask_below": 0.9}})
    assert spec.output.ask_below == 0.9 and spec.to_json()["output"]["ask_below"] == 0.9
    assert Spec.from_json(spec.to_json()) == spec
    plain = Model(Spec.from_json(CASES), k=15, min_sim=0.1)
    for data, outcome in shape_cases(200):
        plain.record(data, outcome)
    queries = [d for d, _ in shape_cases(40, seed=4)]
    tops = sorted(max(plain.decide(q)["probabilities"].values()) for q in queries)
    assert not any(plain.decide(q)["ask"] for q in queries)  # no bar, no costed ask: never asks
    bar = round((tops[10] + tops[30]) / 2, 4)  # between the less and the more confident
    model = Model(Spec.from_json({**CASES, "output": {"ask_below": bar}}), k=15, min_sim=0.1)
    for data, outcome in shape_cases(200):
        model.record(data, outcome)
    decisions = [model.decide(q) for q in queries]
    assert all(d["ask"] == (max(d["probabilities"].values()) < bar) for d in decisions)
    assert any(d["ask"] for d in decisions) and not all(d["ask"] for d in decisions)
    assert [d["outcome"] for d in decisions] == [plain.decide(q)["outcome"] for q in queries]  # the guess stays
    named = Spec.from_json({**CASES, "outputs": {"risk": {"values": ["low", "high"], "ask_below": 0.6}}})
    assert named.output_of("risk").ask_below == 0.6
    with pytest.raises(SpecError, match="ask_below"):
        Spec.from_json({**CASES, "output": {"ask_below": 1.5}})


def test_shortlist_settings_are_checked() -> None:
    spec = Spec.from_json({**CASES, "settings": {"shortlist": 2000, "exact_below": 5000}})
    assert (spec.settings.shortlist, spec.settings.exact_below) == (2000, 5000)
    assert Spec.from_json({**CASES, "settings": {"shortlist": 0}}).settings.shortlist == 0
    with pytest.raises(SpecError, match="shortlist"):
        Spec.from_json({**CASES, "settings": {"shortlist": 50}})
    model = Model(spec)
    assert (model.space.shortlist, model.space.exact_below) == (2000, 5000)


# ── step 1: the storage interface ────────────────────────────────────


def test_a_space_on_a_sqlite_store_is_a_space_on_its_path(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "s.db"))
    assert isinstance(store, Store)
    via_store, via_path = Space(dim=512, store=store), Space(dim=512, path=str(tmp_path / "p.db"))
    for space in (via_store, via_path):
        for i, (data, outcome) in enumerate(shape_cases(40)):
            space.record(data["a"]["s"], outcome, rid=f"r{i}", ts=float(i))
    q = shape_cases(1, seed=3)[0][0]["a"]["s"]
    assert via_store.query(q).to_json() == via_path.query(q).to_json()
    assert via_store.path == store.path
    with pytest.raises(ValueError):
        Space(path=str(tmp_path / "x.db"), store=store)


def test_load_false_on_a_store_that_cannot_shortlist_reads_exactly(tmp_path) -> None:
    path = str(tmp_path / "l.db")
    with Space(dim=512, store=SqliteStore(path)) as w:
        for i, (data, outcome) in enumerate(shape_cases(40)):
            w.record(data["a"]["s"], outcome, rid=f"r{i}")
    lazy = Space(dim=512, store=SqliteStore(path), load=False)
    assert not lazy.loaded and len(lazy) == 40 and lazy._n == 0
    lazy.record({"color": "r"}, "good", rid="new")  # a write goes to the store, nothing loaded
    assert not lazy.loaded and len(lazy) == 41 and lazy.holds(["new", "r1", "zz"]) == {"new", "r1"}
    q = {"color": "r", "shape": "sq"}
    assert lazy.query(q).to_json() == Space(dim=512, store=SqliteStore(path)).query(q).to_json() and lazy.loaded


def test_the_bits_are_the_glyphs() -> None:
    from glyphh_postgres import bit_sim, pack, unpack

    rng = np.random.default_rng(1)
    for dim in (256, 1000, 4096):
        a, b = (rng.integers(0, 2, dim).astype(np.int8) * 2 - 1 for _ in range(2))
        assert np.array_equal(unpack(pack(a), dim), a)
        assert len(pack(a)) == (dim + 7) // 8
        assert abs(bit_sim(a, b) - kernel.sim(a, b)) < 1e-9


# ── PostgresStore ────────────────────────────────────────────────────


@pytest.fixture
def pg():
    import psycopg

    schema = f"ts_{uuid.uuid4().hex[:12]}"
    conn = psycopg.connect(POSTGRES, autocommit=True)
    yield conn, schema
    conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    conn.close()


def _pg_model(pg, name: str, spec: dict, **settings) -> Model:
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    spec = {**spec, "settings": {**spec.get("settings", {}), **settings}}
    return Model(Spec.from_json(spec), store=PostgresStore(conn, schema, name, dim=spec["dimension"]))


@pytest.mark.postgres
def test_postgres_holds_what_sqlite_holds(pg, tmp_path) -> None:
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    on_pg = Space(dim=512, seed=4, store=PostgresStore(conn, schema, "same", dim=512))
    on_file = Space(dim=512, seed=4, store=SqliteStore(str(tmp_path / "same.db")))
    for space in (on_pg, on_file):
        for i, (data, outcome) in enumerate(shape_cases(60)):
            space.record(data["a"]["s"], outcome, rid=f"r{i % 50}", ts=float(i % 7), outcomes={"risk": "high" if i % 3 else "low"})
        space.grade("r4", "risk", None)
        space.grade("r5", None, "good")
        space.forget("r6")
        space.set_meta("learned", {"b": 1, "a": [1, 2.5, "x"]})
        space.calibrate(sample=20)
    pg_again = Space(dim=512, seed=4, store=PostgresStore(conn, schema, "same", dim=512))
    file_again = Space(dim=512, seed=4, store=SqliteStore(str(tmp_path / "same.db")))
    assert pg_again._ids == file_again._ids and pg_again._outcomes == file_again._outcomes
    assert pg_again._named == file_again._named and pg_again._situations == file_again._situations
    assert np.array_equal(pg_again._matrix[: pg_again._n], file_again._matrix[: file_again._n])
    assert pg_again.tau == file_again.tau and pg_again.meta("learned") == file_again.meta("learned")
    assert pg_again.store.count() == 49 and pg_again.store.count_graded("risk") == file_again.store.count_graded("risk")
    q = {"color": "r", "shape": "ci", "size": ["0", "1", "2"]}
    assert pg_again.query(q).to_json() == file_again.query(q).to_json()


@pytest.mark.postgres
def test_a_shortlisted_read_is_the_exact_read_when_the_shortlist_holds_the_top(pg) -> None:
    exact = _pg_model(pg, "exact", CASES, shortlist=0)
    short = _pg_model(pg, "short", CASES, exact_below=0, shortlist=100)
    whole = _pg_model(pg, "whole", CASES, exact_below=0, shortlist=10000)  # the shortlist is every precedent
    cases = shape_cases(400)
    for model in (exact, short, whole):
        model.record_many([{"data": d, "outcome": o, "ts": float(i)} for i, (d, o) in enumerate(cases)])
    queries = [d for d, _ in shape_cases(30, seed=8)]
    for q in queries:
        assert whole.query(q).to_json() == exact.query(q).to_json()
        assert whole.probabilities(q) == exact.probabilities(q)
        assert whole.facts(q, top=5) == exact.facts(q, top=5)
    assert not short.space.loaded and not whole.space.loaded and exact.space.loaded
    same = sum(short.decide(q) == exact.decide(q) for q in queries)
    assert same >= 27  # 100 of 400 nearest by Hamming: nearly always the exact answer
    rid = short.record(cases[0][0], "bad")  # writes go to the store
    assert not short.space.loaded and short.space.store.count() == 400 and rid


@pytest.mark.postgres
def test_named_outputs_read_through_their_view_of_the_shortlist(pg) -> None:
    spec = {**TEXT, "outputs": {"team": {"values": ["a", "b"]}}}
    exact = _pg_model(pg, "nx", spec, shortlist=0)
    short = _pg_model(pg, "ns", spec, exact_below=0, shortlist=10000)
    for model in (exact, short):
        model.record_many(
            [{"data": d, "outcome": o, "outcomes": {"team": "a" if o == "lost" else "b"}, "ts": float(i)} for i, (d, o) in enumerate(text_cases())]
        )
        model.learn()
    short = _pg_model(pg, "ns", spec, exact_below=0, shortlist=10000)  # as a fresh worker reads it: nothing held
    assert not short.space.loaded and short._specs
    for text in ("card missing", "exchange rate please"):
        q = {"m": {"b": {"text": text, "id": "q"}}}
        assert short.probabilities(q, output="team") == exact.probabilities(q, output="team")
        assert short.decide(q) == exact.decide(q)


@pytest.mark.postgres
def test_an_org_schema_sees_only_its_own(pg) -> None:
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    other = schema + "_b"
    try:
        a = Space(dim=256, store=PostgresStore(conn, schema, "m", dim=256))
        b = Space(dim=256, store=PostgresStore(conn, other, "m", dim=256))
        a.record({"x": "secret"}, "a-only", rid="r1")
        assert len(b) == 0 and b.query({"x": "secret"}).count == 0
        m2 = Space(dim=256, store=PostgresStore(conn, schema, "m2", dim=256))
        assert len(m2) == 0  # another model in the same org: its own partition
        with pytest.raises(ValueError):
            PostgresStore(conn, 'x"; DROP SCHEMA public; --', "m")
    finally:
        conn.execute(f'DROP SCHEMA IF EXISTS "{other}" CASCADE')


@pytest.mark.postgres
def test_an_rrotor_file_merges_into_postgres(pg, tmp_path) -> None:
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    path = str(tmp_path / "precedents.sqlite")
    with Space(dim=512, store=SqliteStore(path)) as f:
        for i, (data, outcome) in enumerate(shape_cases(30)):
            f.record(data["a"]["s"], outcome, rid=f"r{i}", outcomes={"risk": "x"})
    cloud = Space(dim=512, store=PostgresStore(conn, schema, "imported", dim=512))
    assert cloud.merge(SqliteStore(path, readonly=True)) == 30
    back = Space(dim=512, store=PostgresStore(conn, schema, "imported", dim=512))
    file = Space(dim=512, store=SqliteStore(path))
    assert back._ids == file._ids and back._named == file._named
    assert np.array_equal(back._matrix[:30], file._matrix[:30])


@pytest.mark.postgres
def test_a_readonly_postgres_store_refuses_writes(pg) -> None:
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    Space(dim=256, store=PostgresStore(conn, schema, "ro", dim=256)).record({"x": "1"}, "o")
    reader = Space(dim=256, store=PostgresStore(conn, schema, "ro", dim=256, readonly=True))
    assert reader.readonly and len(reader) == 1
    with pytest.raises(ReadOnlyError):
        reader.record({"x": "2"}, "o")
    with pytest.raises(ValueError):
        PostgresStore(conn, schema, "never-made", dim=256, readonly=True)


@pytest.mark.postgres
def test_the_index_is_dropped_and_built_again(pg) -> None:
    model = _pg_model(pg, "idx", CASES, exact_below=0, shortlist=100)
    store = model.space.store
    store.drop_index()
    model.record_many([{"data": d, "outcome": o} for d, o in shape_cases(300)])
    q = shape_cases(1, seed=5)[0][0]
    without = model.probabilities(q)
    store.build_index()
    conn, schema = store._conn, store.schema
    found = conn.execute("SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexdef LIKE '%%hnsw%%'", (schema,)).fetchone()[0]
    assert found == 1 and model.probabilities(q).keys() == without.keys()
    store.drop()
    assert conn.execute("SELECT to_regclass(%s)", (f'"{schema}".{store._t["part_name"].as_string(conn)}',)).fetchone()[0] is None


@pytest.mark.postgres
def test_a_precedent_is_found_by_its_id_through_an_index(pg) -> None:
    """grade, forget, has and rewrite look a precedent up by id alone: each partition indexes its ids, so a lookup
    is an index probe, not a scan of the primary key (model, id) it cannot lead with. With or without the HNSW
    index, and kept when that one is dropped."""
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    for name, index in (("with", True), ("without", False)):
        store = PostgresStore(conn, schema, name, dim=256, index=index)
        Space(dim=256, store=store).record({"x": "1"}, "o", rid="r1")
        store.drop_index()
        part = store._t["part_name"].as_string(conn).strip('"')
        found = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = %s", (schema, f"{part}_id")
        ).fetchone()
        assert found is not None and found[0].startswith("CREATE UNIQUE INDEX") and found[0].endswith("(id)")
        conn.execute("SET enable_seqscan = off")
        plan = conn.execute(f'EXPLAIN SELECT 1 FROM "{schema}"."{part}" WHERE id = %s', ("r1",)).fetchall()
        conn.execute("RESET enable_seqscan")
        assert f"{part}_id" in " ".join(r[0] for r in plan)
        PostgresStore(conn, schema, name, dim=256)  # opened again: the index is there already


@pytest.mark.postgres
def test_a_store_made_opens_without_waiting_for_its_writers(pg) -> None:
    """Opening a store that is all there makes no DDL: it never waits on a write open on its partition (a CREATE
    INDEX IF NOT EXISTS would, for its ShareLock), nor holds the schema's setup lock."""
    import psycopg
    from glyphh_postgres import PostgresStore

    conn, schema = pg
    store = PostgresStore(conn, schema, "busy", dim=256)
    Space(dim=256, store=store).record({"x": "1"}, "o", rid="r1")
    bare = PostgresStore(conn, schema, "bare", dim=256, index=False)  # its HNSW index still to make
    writer = psycopg.connect(POSTGRES)
    reader = psycopg.connect(POSTGRES, autocommit=True)
    try:
        for each in (store, bare):  # a write in flight on each, not committed
            writer.execute(each._q("LOCK TABLE {part} IN ROW EXCLUSIVE MODE"))
        reader.execute("SET lock_timeout = '500ms'")
        assert PostgresStore(reader, schema, "busy", dim=256).count() == 1
        with pytest.raises(psycopg.errors.LockNotAvailable):  # one with something to make waits, as before
            PostgresStore(reader, schema, "bare", dim=256, index=True)
    finally:
        writer.rollback()
        writer.close()
        reader.close()
    assert PostgresStore(conn, schema, "bare", dim=256, index=True).count() == 0  # and makes it once free
