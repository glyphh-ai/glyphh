"""A store opened read-only (kernel 3.10): a follower's copy on a read-only disk. Every read works from a file opened
mode=ro in a folder no one may write; every write raises ReadOnlyError (E_READ_ONLY) before the file is touched;
nothing is ever created beside it."""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import stat
from pathlib import Path

import numpy as np
import pytest

import glyphh_kernel as kernel
from glyphh_kernel import ENCODING, ReadOnlyError, Space, decide, reencode_store, symbol
from glyphh_spec import Model, Spec

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


def case(i: int, purpose: str, amount: int, notes: str = "a note") -> dict:
    return {"loan": {"ask": {"purpose": purpose, "amount": amount, "notes": notes, "id": f"c{i}"}}}


def cases() -> list[tuple[dict, str]]:
    rng = random.Random(1)
    out = []
    for i in range(60):
        purpose = rng.choice(["car", "home"])
        notes = "new car loan" if purpose == "car" else "a house to live in"
        out.append((case(i, purpose, rng.choice([500, 2500, 7500]), notes), "bad" if purpose == "car" else "good"))
    return out


def snapshot(folder: Path) -> dict[str, str]:
    """Every file in the folder and its content's hash: what a read-only open must leave exactly as it was."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def lock(folder: Path) -> None:
    for p in folder.iterdir():
        p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def unlock(folder: Path) -> None:
    folder.chmod(stat.S_IRWXU)
    for p in folder.iterdir():
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)


@pytest.fixture
def locked(tmp_path):
    """A model's store, learned, calibrated and configured by a writer, then closed (the WAL checkpointed away) and
    its folder made read-only. Yields the folder, the store's path and what the writer read."""
    if os.geteuid() == 0:
        pytest.skip("root writes through a read-only folder")
    folder = tmp_path / "data"
    store = folder / "precedents.sqlite"
    writer = Model(Spec.from_json(SPEC), path=str(store), author="head")
    for data, outcome in cases():
        writer.record(data, outcome)
    writer.configure(word_evidence=1.5)
    writer.learn()
    writer.calibrate(sample=30)
    writer.record(case(500, "car", 500, "remember this"))  # a memory: no outcome
    probe = case(900, "car", 2500, "new car")
    seen = {
        "query": writer.query(probe).to_json(),
        "facts": writer.facts(probe),
        "probabilities": writer.probabilities(probe),
        "decide": writer.decide(probe),
        "settings": writer.settings.to_json(all=True),
        "tau": writer.space.tau,
        "len": len(writer),
    }
    writer.space.close()
    assert sorted(p.name for p in folder.iterdir()) == ["precedents.sqlite"]  # the WAL is gone: no writer has it
    with open(store, "rb") as f:
        assert f.read(20)[18] == 2  # still a WAL-mode file
    lock(folder)
    yield folder, store, probe, seen
    unlock(folder)


def test_every_read_works_on_a_read_only_folder_and_nothing_is_created(locked):
    folder, store, probe, seen = locked
    before = snapshot(folder)
    with pytest.raises(sqlite3.OperationalError):  # what the kernel guards against: plain mode=ro fails here
        db = sqlite3.connect(f"{store.as_uri()}?mode=ro", uri=True)
        try:
            db.execute("SELECT COUNT(*) FROM precedents").fetchone()
        finally:
            db.close()
    model = Model(Spec.from_json(SPEC), path=str(store), readonly=True)
    assert model.readonly and model.space.readonly
    assert len(model) == seen["len"]
    assert model.space.tau == seen["tau"]
    assert model.query(probe).to_json() == seen["query"]
    assert model.facts(probe) == seen["facts"]
    assert model.probabilities(probe) == seen["probabilities"]
    assert model.decide(probe) == seen["decide"]
    assert model.settings.to_json(all=True) == seen["settings"]
    assert model.configure() == seen["settings"]  # no changes: a read
    assert model.space.meta("learned") is not None and model.space.meta("settings") == {"word_evidence": 1.5}
    assert model.space.refresh() == 0
    situation = model.spec.situation(probe)
    assert model.space.answers(situation)
    assert model.space.evidence(situation, "bad").count > 0
    assert model.space.matches(situation, "bad") > 0
    assert decide(model.space, model.space, situation).reason in ("vetoed", "reflex", "low_confidence", "uncalibrated")
    assert model.space.graded()
    model.space.close()
    assert snapshot(folder) == before


def test_every_write_is_refused_before_the_file_is_touched(locked, tmp_path):
    folder, store, probe, _ = locked
    before = snapshot(folder)
    model = Model(Spec.from_json(SPEC), path=str(store), readonly=True)
    other = tmp_path / "other.db"
    with Space(dim=2048, seed=3, path=str(other)) as donor:
        donor.record({"x": "y"}, "z")
    writes = {
        "record": lambda: model.record(case(1000, "home", 500), "good"),
        "learn": model.learn,
        "calibrate": lambda: model.calibrate(sample=20),
        "refresh": model.refresh,
        "configure": lambda: model.configure(k=7),
    }
    space = model.space
    space_writes = {
        "record": lambda: space.record({"x": "y"}, "z"),
        "merge": lambda: space.merge(str(other)),
        "calibrate": lambda: space.calibrate(sample=20),
        "set_meta": lambda: space.set_meta("tau", 1),
        "rewrite": lambda: space.rewrite(lambda s: s),
    }
    for name, write in [*writes.items(), *space_writes.items()]:
        with pytest.raises(ReadOnlyError) as err:
            write()
        assert err.value.code == "E_READ_ONLY" and err.value.operation == name
        assert err.value.path == str(store) and "E_READ_ONLY" in str(err.value) and name in str(err.value)
        assert not isinstance(err.value, sqlite3.Error)
    assert len(model) == len(cases()) + 1 and model.settings.k != 7  # nothing changed in memory either
    with pytest.raises(ReadOnlyError) as err:
        reencode_store(str(store), dim=2048, seed=3)
    assert err.value.operation == "reencode_store"
    space.close()
    assert snapshot(folder) == before


def test_a_wal_store_in_a_writable_folder_gets_no_wal_or_shm(tmp_path):
    path = tmp_path / "s.db"
    with Space(path=str(path)) as w:
        for i in range(5):
            w.record({"task": "t", "n": str(i)}, "ok")
    before = snapshot(tmp_path)
    with Space(path=str(path), readonly=True) as r:
        assert r.query({"task": "t", "n": "1"}).top == "ok"
        r.refresh()
    assert snapshot(tmp_path) == before


def test_a_live_writer_is_read_through_its_wal_and_refresh_sees_new_rows(tmp_path):
    path = tmp_path / "s.db"
    writer = Space(path=str(path))
    writer.record({"task": "a"}, "one")
    names = sorted(p.name for p in tmp_path.iterdir())
    reader = Space(path=str(path), readonly=True)
    assert len(reader) == 1
    writer.record({"task": "b"}, "two")
    assert reader.refresh() == 1 and reader.query({"task": "b"}).top == "two"
    assert sorted(p.name for p in tmp_path.iterdir()) == names
    reader.close()
    writer.close()


def test_a_store_written_after_a_closed_open_is_seen_on_refresh(tmp_path):
    """Read immutable when no writer holds the WAL, a store is reconnected on every refresh, so it stays current."""
    path = tmp_path / "s.db"
    with Space(path=str(path)) as w:
        w.record({"task": "a"}, "one")
    reader = Space(path=str(path), readonly=True)
    with Space(path=str(path)) as w:
        w.record({"task": "b"}, "two")
    assert reader.refresh() == 1 and len(reader) == 2
    reader.close()


def test_no_store_yet_reads_empty_and_makes_nothing(tmp_path):
    path = tmp_path / "missing" / "precedents.sqlite"
    model = Model(Spec.from_json(SPEC), path=str(path), readonly=True)
    assert len(model) == 0 and model.probabilities(case(1, "car", 500)) == {}
    assert model.decide(case(1, "car", 500))["ask"] is True
    assert model.space.meta("learned") is None
    with pytest.raises(ReadOnlyError):
        model.record(case(1, "car", 500), "bad")
    assert not path.parent.exists()


def test_an_older_encoding_is_reencoded_in_memory_only(tmp_path):
    path = tmp_path / "v1.db"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE precedents (id TEXT PRIMARY KEY, situation TEXT NOT NULL, outcome TEXT NOT NULL,"
        " dim INTEGER NOT NULL, glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon')"
    )
    db.execute(
        "INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
        ("r1", '{"task": "x", "constraint": "y"}', "out", 4096, np.ones(4096, dtype=np.int8).tobytes(), "a"),
    )
    db.commit()
    db.close()
    before = snapshot(tmp_path)
    lock(tmp_path)
    try:
        with Space(path=str(path), readonly=True) as space:
            answer = space.query({"task": "x", "constraint": "y"})
            assert answer.top == "out" and answer.receipts[0][1] > 0.99
            assert space._ts == [0.0] and space._authors == ["a"]
    finally:
        unlock(tmp_path)
    assert snapshot(tmp_path) == before
    db = sqlite3.connect(path)
    assert db.execute("SELECT name FROM sqlite_master WHERE name = 'meta'").fetchone() is None  # no schema made
    db.close()
    assert ENCODING > 1


def test_a_restatement_on_open_stays_in_memory(tmp_path):
    """A model whose settings changed what a bag carries restates its store on open; read-only, only in memory."""
    path = tmp_path / "s.db"
    writer = Model(Spec.from_json(SPEC), path=str(path))
    for data, outcome in cases():
        writer.record(data, outcome)
    writer.space.close()
    with Space(dim=2048, seed=3, path=str(path)) as raw:  # learned word weights the rows were not written under
        raw.set_meta("learned", Spec.from_json(SPEC).learn(writer.space.graded()))
    before = snapshot(tmp_path)
    reader = Model(Spec.from_json(SPEC), path=str(path), readonly=True)
    assert any(isinstance(s["loan"]["ask"]["notes"], list) and s["loan"]["ask"]["notes"] and isinstance(s["loan"]["ask"]["notes"][0], list) for s in reader.space._situations)
    reader.space.close()
    assert snapshot(tmp_path) == before
    db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    stored = [json.loads(row[0]) for row in db.execute("SELECT situation FROM precedents")]
    db.close()
    assert stored != reader.space._situations[: len(stored)] or len(stored) != len(reader.space._situations)


def test_readonly_events_and_symbols_read_back(tmp_path):
    path = tmp_path / "s.db"
    events = [symbol("deploy"), symbol("rollback")]
    with Space(path=str(path)) as w:
        for i in range(3):
            w.record({"task": "ship"}, "canary", events=events)
    with Space(path=str(path), readonly=True) as r:
        assert r.query({"task": "ship"}, events=events).count == 3
        assert r.facts({"task": "ship"}, events=events)[0].root.to_json()
    assert kernel.ReadOnlyError.code == "E_READ_ONLY"
