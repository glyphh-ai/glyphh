"""Courier grades peers' pending claims by REPRODUCING them with its own seed.

    python3 agents/courier/grade.py            # grade everything I can reproduce
    python3 agents/courier/grade.py --dry      # show what I would grade

Instruments (never the claim author's own verdict):
  <author>/claims.py measure(q, my_seed)   peers' published measurements
  memory/world.py measure(q, my_seed)      world questions (bundle/strand/nest),
                                           incl. reasoner's inferred points
  concept part_of                          my own expansion of the codebook
                                           definition (protocol.expand)
  *_py status v1_ready                     import + a round trip in a private world
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import zlib
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS / "shared"))
sys.path.insert(0, str(AGENTS))
from knowledge import KB  # noqa: E402

_MODS = {}


def _load(agent: str, name: str):
    key = (agent, name)
    if key not in _MODS:
        path = AGENTS / agent / f"{name}.py"
        mod = None
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"{agent}_{name}", path)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(path.parent))
            spec.loader.exec_module(mod)
        _MODS[key] = mod
    return _MODS[key]


def my_seed(cid: str) -> int:
    return 9000 + zlib.crc32(cid.encode()) % 100000


def _contains(m, name, lx, depth=0):
    import protocol as P
    if depth > 40:
        return False
    if m == name:
        return True
    if isinstance(m, str) and m in lx.concepts:
        return _contains(lx.concepts[m]["meaning"], name, lx, depth + 1)
    if isinstance(m, dict):
        return any(_contains(v, name, lx, depth + 1) for v in m.values())
    if isinstance(m, list):
        return any(_contains(v, name, lx, depth + 1) for v in m)
    return False


def reproduce(c):
    """The value I get for claim c in my own world, or None (can't test)."""
    q = (c.subject, c.relation, dict(c.context))
    seed = my_seed(c.id)
    if c.relation == "status" and c.value == "v1_ready":
        return _smoke(c.subject)
    if c.relation == "part_of":
        from language import Lexicon
        lx = Lexicon(path=AGENTS / "shared" / "codebook.jsonl", author="courier")
        if c.value in lx.concepts and c.subject in lx.concepts:
            # subject is part of obj iff obj's definition reaches subject
            m = lx.concepts[c.value]["meaning"]
            return c.value if _contains(m, c.subject, lx) else "not_part"
        return None
    world = _load("memory", "world")
    if world and ((c.subject, c.relation) in getattr(world, "FAMILIES", {})
                  or (c.subject, c.relation) == ("situation", "overlap_sim")):
        return world.measure(q, seed)
    mod = _load(c.author, "claims")
    if mod is not None and hasattr(mod, "measure"):
        try:
            return str(mod.measure(q, seed))
        except (KeyError, ValueError):
            return None
    return None


def _smoke(subject: str):
    if subject == "language_py":
        from language import Lexicon
        lx = Lexicon(path=None, seed=4321)
        m = {"subject": "a", "relation": "b", "object": {"x": "y", "z": "w"}}
        return "v1_ready" if lx.decode(lx.encode(m)) == m else "broken"
    if subject == "knowledge_py":
        with tempfile.TemporaryDirectory() as d:
            kb = KB(root=d)
            cid = kb.tell("x", "s", "r", "o")
            kb.grade("y", cid, True)
            ok = kb.ask("s", "r", asker="z").value == "o"
            kb.close()
        return "v1_ready" if ok else "broken"
    return None


def main(dry=False):
    kb = KB()
    pend = kb.pending("courier", limit=1000)
    tally = {"ok": 0, "refuted": 0, "untested": 0}
    for c in pend:
        try:
            got = reproduce(c)
        except Exception as e:  # an instrument that crashes is "can't test"
            print(f"  ! {c.id} {c.subject} {c.relation}: {type(e).__name__}: {e}")
            got = None
        if got is None:
            tally["untested"] += 1
            print(f"  ? {c.id} {c.author} {c.subject} {c.relation} {c.context} -> {c.value}")
            continue
        ok = str(got) == c.value
        tally["ok" if ok else "refuted"] += 1
        print(f"  {'+' if ok else 'X'} {c.id} {c.author} {c.subject} {c.relation} "
              f"{c.context} claimed={c.value} mine={got}")
        if not dry:
            kb.grade("courier", c.id, ok,
                     f"courier reproduced with seed {my_seed(c.id)}" if ok else
                     f"courier seed {my_seed(c.id)}: got {got!r}, claimed {c.value!r}")
    print(tally)
    return tally


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
