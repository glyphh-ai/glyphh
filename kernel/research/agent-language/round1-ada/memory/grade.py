"""memory grades peers' pending claims by REPRODUCING them in its own world.

    python3 agents/memory/grade.py [--dry]

Instruments (never the author's verdict):
  <author>/claims.py measure(q, my_seed)   a peer's published measurement,
                                           re-run with MY seed
  memory/world.py measure(q, my_seed)      world questions (bundle/strand/
                                           nest/situation), incl. inferences
  (c:X, part_of, c:Y)                      read FROM THE GLYPH: decode the
                                           glyph of Y with the language and
                                           look for X in the reading, recursing
                                           into concepts it reads as (depth 6)
Claims I have no instrument for are left ungraded (never guessed).
"""

from __future__ import annotations

import importlib.util
import sys
import zlib
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS / "shared"))
sys.path.insert(0, str(AGENTS / "memory"))

from knowledge import KB, Claim  # noqa: E402

_MODS = {}


def _load(agent: str):
    if agent not in _MODS:
        path = AGENTS / agent / "claims.py"
        mod = None
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"{agent}_claims", path)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(path.parent))
            spec.loader.exec_module(mod)
        _MODS[agent] = mod
    return _MODS[agent]


def my_seed(cid: str) -> int:
    return 5000 + zlib.crc32(("memory:" + cid).encode()) % 100000


def _reads_as(glyph, name, lx, depth=0, seen=None):
    """Does reading `glyph` (recursively through concepts it reads as)
    reach concept `name`?"""
    seen = seen if seen is not None else set()
    if depth > 6:
        return False
    m = lx.decode(glyph)
    names = []

    def walk(x):
        if isinstance(x, str):
            names.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(m)
    if name in names:
        return True
    for n in names:
        if n in lx.concepts and n not in seen:
            seen.add(n)
            if _reads_as(lx.encode(n), name, lx, depth + 1, seen):
                return True
    return False


def reproduce(c: Claim):
    import world
    q = (c.subject, c.relation, c.context)
    seed = my_seed(c.id)
    if c.relation == "part_of" and c.subject.startswith("c:"):
        from language import Lexicon
        lx = Lexicon(author="memory")
        lx.refresh()
        if c.value not in lx.concepts:
            return None
        return c.value if _reads_as(lx.encode(c.value), c.subject, lx) \
            else "not_part"
    if (c.subject, c.relation) in world.FAMILIES or \
            (c.subject, c.relation) == ("situation", "overlap_sim"):
        return world.measure(q, seed)
    mod = _load(c.author)
    if mod is None or not hasattr(mod, "measure"):
        return None
    try:
        return mod.measure(q, seed)
    except (KeyError, ValueError, TypeError) as e:
        print("  no instrument:", c.id, e)
        return None


def main(dry: bool = False) -> None:
    kb = KB()
    todo = kb.pending("memory", limit=1000)
    tally = {"ok": 0, "refuted": 0, "skipped": 0}
    for c in todo:
        if dry:
            print(c.id, c.author, c.subject, c.relation, c.context, c.value)
            continue
        ok = kb.verify("memory", c.id, reproduce,
                       how=f"memory reproduced, seed {my_seed(c.id)}")
        key = "skipped" if ok is None else ("ok" if ok else "refuted")
        tally[key] += 1
        print(f"{key:8s} {c.id} {c.author} {c.subject} {c.relation} "
              f"{c.context} -> {c.value}")
    print(tally)


if __name__ == "__main__":
    main("--dry" in sys.argv)
