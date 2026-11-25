"""The codebook's concept structure as graded knowledge.

    python3 agents/lexicon/concepts.py tell     # file part_of facts (author=lexicon)
    python3 agents/lexicon/concepts.py grade <you>   # grade others' part_of claims

Every concept in shared/codebook.jsonl has a definition (a meaning);
names of other concepts inside it are its parts. `(child, part_of,
parent)` is a fact anyone can reproduce by reading the definitions, and
part_of is transitive, so reasoner's closure can derive
`(child, part_of, grandparent)` and anyone can grade that by expanding
the grandparent's definition. Only children with ONE parent are told:
the KB answers one object per (subject, relation).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional

_AGENTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_AGENTS / "shared"))
from language import Lexicon  # noqa: E402


def parts(meaning, lx: Lexicon) -> Iterator[str]:
    """Concept names used directly inside a definition."""
    if isinstance(meaning, str):
        if meaning in lx.concepts:
            yield meaning
    elif isinstance(meaning, dict):
        for v in meaning.values():
            yield from parts(v, lx)
    elif isinstance(meaning, (list, tuple)):
        for v in meaning:
            yield from parts(v, lx)


def parents(lx: Lexicon) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p, c in lx.concepts.items():
        for ch in set(parts(c["meaning"], lx)):
            out.setdefault(ch, []).append(p)
    return out


def contains(parent: str, child: str, lx: Lexicon, _seen=None) -> bool:
    """Does parent's definition, expanded recursively, use child?"""
    _seen = _seen or set()
    if parent in _seen or parent not in lx.concepts:
        return False
    _seen.add(parent)
    for ch in parts(lx.concepts[parent]["meaning"], lx):
        if ch == child or contains(ch, child, lx, _seen):
            return True
    return False


def reproduce(subject: str, obj: str, lx: Optional[Lexicon] = None) -> str:
    """The grader's measurement for (subject, part_of, obj): returns obj
    if obj's expanded definition contains subject, else 'not_part'."""
    lx = lx or Lexicon(author="grader")
    lx.refresh()
    return obj if contains(obj, subject, lx) else "not_part"


def tell_all() -> List[str]:
    from knowledge import KB
    kb, lx = KB(), Lexicon(author="lexicon")
    told = {(c.subject, c.relation) for c in kb.all_claims()}
    out = []
    for child, ps in sorted(parents(lx).items()):
        if len(ps) != 1 or (child, "part_of") in told:
            continue
        cid = kb.tell("lexicon", child, "part_of", ps[0],
                      how="python3 agents/lexicon/concepts.py: "
                          "reproduce(subject, object) over shared/codebook.jsonl")
        out.append(cid)
        print(cid, child, "part_of", ps[0])
    return out


def grade_all(grader: str = "lexicon") -> None:
    from knowledge import KB
    kb, lx = KB(), Lexicon(author=grader)
    for c in kb.pending(grader, 500):
        if c.relation != "part_of" or not c.subject.startswith("c:"):
            continue
        ok = kb.verify(grader, c.id, lambda cl: reproduce(cl.subject, cl.value, lx),
                       how="expanded the object's definition in the codebook")
        print(c.id, c.subject, "part_of", c.value, ok)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "tell":
        tell_all()
    elif cmd == "grade":
        grade_all(sys.argv[2] if len(sys.argv) > 2 else "lexicon")
    else:
        print(__doc__)
