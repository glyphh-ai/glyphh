"""Reference values from the Python kernel, for test/parity.test.mjs.

Usage: python parity_ref.py vectors            -> JSON of glyph hashes
       python parity_ref.py write <dir>        -> writes stores for JS to read
       python parity_ref.py read <dir>         -> reads the stores JS wrote
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from glyphh_kernel import (Space, Strand, bind, bundle, decide, roll, sim,  # noqa: E402
                           symbol)


def h(g):
    return hashlib.sha256(g.tobytes()).hexdigest()


KEYS = ["a", "b", "attr:task", "val:deploy", "é", "\U0001F642", "", "x" * 300]
SITUATIONS = [
    {"task": "deploy", "env": "prod"},
    {"b": "2", "a": "1", "c": "3", "d": "4"},
    {"é": "ü", "Z": "z", "a": "\U0001F642"},
    {f"k{i}": f"v{i}" for i in range(9)},
    {"only": "one"},
]


def vectors():
    out = {"symbols": {}, "ops": {}, "encode": {}, "sims": {}}
    for key in KEYS:
        for seed, dim in ((42, 4096), (7, 1000), (42, 64)):
            out["symbols"][f"{seed}|{dim}|{key}"] = h(symbol(key, seed, dim))
    a, b, c, d, e = (symbol(k) for k in "abcde")
    out["ops"]["bind"] = h(bind(a, b))
    for k in (1, 3, -5, 4096, 4099):
        out["ops"][f"roll{k}"] = h(roll(a, k))
    out["ops"]["bundle2"] = h(bundle([a, b]))
    out["ops"]["bundle3"] = h(bundle([a, b, c]))
    out["ops"]["bundle4"] = h(bundle([a, b, c, d]))
    out["ops"]["bundle4rev"] = h(bundle([d, c, b, a]))
    out["ops"]["bundle5"] = h(bundle([a, b, c, d, e]))
    out["ops"]["bundle_dup"] = h(bundle([a, a, b, b]))
    for decay in (0.7, 0.2, 1.0):
        out["ops"][f"strand{decay}"] = h(Strand([a, b, c, d]).state(decay))
    out["ops"]["strand1"] = h(Strand([a]).state())
    space = Space()
    ev = [symbol("up"), symbol("down"), symbol("up")]
    for i, s in enumerate(SITUATIONS):
        out["encode"][str(i)] = h(space.encode(s))
        out["encode"][f"{i}+ev"] = h(space.encode(s, events=ev))
    out["sims"]["ab"] = sim(a, b)
    out["sims"]["enc01"] = sim(space.encode(SITUATIONS[0]),
                               space.encode({"task": "deploy", "env": "dev"}))
    return out


def write(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    ev = [symbol("up"), symbol("down")]
    wins = Space(min_sim=0.4, author="py-a", path=str(root / "wins.db"))
    vetoes = Space(min_sim=0.4, author="py-b", path=str(root / "vetoes.db"))
    base = {"task": "deploy", "env": "prod"}
    for i in range(3):
        wins.record(base, "canary", ts=10.0 + i)
    wins.record({"task": "deploy", "env": "dev"}, "yolo", ts=5.0)
    wins.record({"kind": "flap"}, "scale_down", events=ev, ts=6.0)
    for m in ("os", "json", "numpy"):
        for g in ("a", "b", "c"):
            wins.author = g
            wins.record({"file": "app.py", "rel": "imports"}, m, ts=7.0)
    vetoes.record(base, "canary", ts=20.0)
    wins.close(); vetoes.close()


def answers(root: Path, prefix: str):
    wins = Space(min_sim=0.4, path=str(root / f"{prefix}wins.db"))
    vetoes = Space(min_sim=0.4, path=str(root / f"{prefix}vetoes.db"))
    base = {"task": "deploy", "env": "prod"}
    ev = [symbol("up"), symbol("down")]
    out = {
        "glyphs": sorted(h(g) for g in wins._glyphs),
        "query": wins.query(base).to_json(),
        "decide": decide(wins, vetoes, base).to_json(),
        "answers": [e.to_json() for e in wins.answers(
            {"file": "app.py", "rel": "imports"}, min_count=3)],
        "flap": wins.query({"kind": "flap"}, events=ev).to_json(),
        "matches": vetoes.matches(base, "canary"),
    }
    for r in out["query"]["receipts"] + out["flap"]["receipts"]:
        r.pop("id")
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "vectors":
        print(json.dumps(vectors()))
    elif mode == "write":
        write(Path(sys.argv[2]))
    elif mode == "read":
        print(json.dumps(answers(Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")))
