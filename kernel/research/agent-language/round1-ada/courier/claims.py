"""Courier's claims about the protocol, each one a reproducible measurement.

    python3 agents/courier/claims.py measure <subject> <relation> [k=v ...] [--seed N]
    python3 agents/courier/claims.py tell       # file every claim in the KB (author=courier)
    python3 agents/courier/claims.py grade      # grade peers' pending claims I can reproduce

Same shape as lexicon/claims.py: measure(question, seed) -> answer word.
The seed picks the vocabulary (Lexicon(seed=...)) and the random
messages, so agreement across seeds means the property belongs to the
protocol, not to one draw.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

_SHARED = Path(__file__).resolve().parents[1] / "shared"
sys.path.insert(0, str(_SHARED))
sys.path.insert(0, str(_SHARED.parent))
import protocol as P  # noqa: E402
from language import Lexicon  # noqa: E402

Question = Tuple[str, str, Dict[str, str]]
DRAWS = 5
AG = ["lexicon", "courier", "memory", "reasoner"]


def _world(seed: int, n_words: int = 300, n_roles: int = 24):
    lx = Lexicon(path=None, seed=seed, author="courier-claims")
    lx.typed = False
    words = [f"w{i}" for i in range(n_words)]
    roles = [f"r{i}" for i in range(n_roles)]
    for w in words:
        lx.word(w)
    for r in roles:
        lx.role(r)
    return lx, words, roles, random.Random(seed)


def _msg(lx, rng, content, linked):
    reply = thread = None
    if linked:
        reply = P.Message(rng.choice(AG), "all", "ask", "x").glyph(lx)
        thread = P.Conversation([reply]).state()
    return P.Message(rng.choice(AG), rng.choice(AG + ["all"]),
                     rng.choice(P.ACTS), content, reply, thread).glyph(lx)


def _tree(rng, words, roles, m, d):
    f = {r: rng.choice(words) for r in rng.sample(roles, m)}
    if d > 1:
        f[rng.choice(list(f))] = _tree(rng, words, roles, m, d - 1)
    return f


def content_exact(slots: int, linked: bool, chunked: bool, seed: int) -> str:
    """A flat `slots`-slot content in an envelope (with reply_to+thread
    when linked): decoded exactly from the glyph over DRAWS messages?"""
    lx, words, roles, rng = _world(seed)
    for _ in range(DRAWS):
        c = {r: rng.choice(words) for r in rng.sample(roles, slots)}
        sent = P.chunked(c, lx) if chunked else c
        d = P.decode(_msg(lx, rng, sent, linked), lx, depth=0)
        if d.content != c:
            return "lossy"
    return "exact"


def max_depth(chunked: bool, seed: int, top: int = 8) -> str:
    """Deepest nesting (3-slot frames) that decodes exactly inside a
    linked envelope for all DRAWS messages; '0' if even depth 1 fails."""
    lx, words, roles, rng = _world(seed)
    best = 0
    for depth in range(1, top + 1):
        for _ in range(DRAWS):
            t = _tree(rng, words, roles, 3, depth)
            sent = P.chunked(t, lx) if chunked else t
            d = P.decode(_msg(lx, rng, sent, True), lx, depth=depth + 1)
            if d.content != t:
                return str(best)
        best = depth
    return f"{top}_or_more"


def handshake(condition: str, seed: int) -> str:
    """accepted | rejected (majority over 4*DRAWS messages)."""
    lx, words, roles, rng = _world(seed)
    nr = np.random.RandomState(seed)
    acc = 0
    n = DRAWS * 4
    for _ in range(n):
        c = {r: rng.choice(words) for r in rng.sample(roles, 3)}
        if condition == "foreign_seed":
            g = _msg(Lexicon(path=None, seed=seed + 1), rng, c, False)
        elif condition.startswith("bitflip_"):
            p = float(condition.split("_")[1])
            g = _msg(lx, rng, c, False).copy()
            g[nr.random_sample(lx.dim) < p] *= -1
        elif condition == "bare_frame":
            g = lx.encode(c)
        elif condition == "random":
            g = (nr.randint(0, 2, lx.dim) * 2 - 1).astype(np.int8)
        else:
            raise KeyError(condition)
        acc += P.decode(g, lx, read_content=False).valid
    return "accepted" if acc > n / 2 else "rejected"


def reply_resolves(among: int, seed: int) -> str:
    lx, words, roles, rng = _world(seed)
    for _ in range(DRAWS):
        seen = {f"m{i}": _msg(lx, rng, {r: rng.choice(words) for r in rng.sample(roles, 3)}, False)
                for i in range(among)}
        pid = rng.choice(list(seen))
        child = P.Message(rng.choice(AG), "all", "answer", "ok", seen[pid]).glyph(lx)
        if P.decode(child, lx, known_msgs=seen, read_content=False).get("reply_to") != pid:
            return "no"
    return "yes"


def turn_recoverable(age: int, seed: int, length: int = 16) -> str:
    """Can the turn `age` steps back be identified (top-1 among the
    thread's own turns + 100 other messages) from the thread glyph alone,
    in at least 4 of DRAWS threads?"""
    lx, words, roles, rng = _world(seed)
    rand = lambda: _msg(lx, rng, {r: rng.choice(words) for r in rng.sample(roles, 3)}, False)
    ok = 0
    for _ in range(DRAWS):
        turns = [rand() for _ in range(length)]
        pool = turns + [rand() for _ in range(100)]
        probe = P.Conversation(turns).turn(age)
        s = [P.sim(probe, g) for g in pool]
        ok += int(np.argmax(s)) == length - 1 - age
    return "yes" if ok >= DRAWS - 1 else "no"


def fidelity_flags(p: float, seed: int) -> str:
    """Does fidelity (< 0.9) flag a message corrupted at bit-flip rate p
    that still passes the handshake, while clean messages read >= 0.99?"""
    lx, words, roles, rng = _world(seed)
    nr = np.random.RandomState(seed)
    for _ in range(DRAWS):
        c = {r: rng.choice(words) for r in rng.sample(roles, 3)}
        g = _msg(lx, rng, c, False)
        if P.decode(g, lx, depth=0).fidelity < 0.99:
            return "no"
        g = g.copy()
        g[nr.random_sample(lx.dim) < p] *= -1
        d = P.decode(g, lx, depth=0)
        if d.valid and d.fidelity >= 0.9:
            return "no"
    return "yes"


def measure(q: Question, seed: int) -> str:
    s, r, c = q
    yes = lambda k: c.get(k, "no") == "yes"
    if (s, r) == ("envelope_content", "decodes"):
        return content_exact(int(c["slots"]), yes("linked"), yes("chunked"), seed)
    if (s, r) == ("envelope", "max_readable_depth"):
        return max_depth(yes("chunked"), seed)
    if (s, r) == ("handshake", "verdict"):
        return handshake(c["condition"], seed)
    if (s, r) == ("reply_to", "resolves"):
        return reply_resolves(int(c["among"]), seed)
    if (s, r) == ("thread_turn", "recoverable"):
        return turn_recoverable(int(c["age"]), seed)
    if (s, r) == ("fidelity", "flags_corruption"):
        return fidelity_flags(float(c["p"]), seed)
    raise KeyError(q)


QUESTIONS = (
    [("envelope_content", "decodes", {"slots": "3", "linked": "yes", "chunked": "no"}),
     ("envelope_content", "decodes", {"slots": "4", "linked": "no", "chunked": "no"}),
     ("envelope_content", "decodes", {"slots": "8", "linked": "yes", "chunked": "no"}),
     ("envelope_content", "decodes", {"slots": "12", "linked": "yes", "chunked": "yes"}),
     ("envelope", "max_readable_depth", {"chunked": "yes"}),
     ("envelope", "max_readable_depth", {"chunked": "no"}),
     ("handshake", "verdict", {"condition": "foreign_seed"}),
     ("handshake", "verdict", {"condition": "bare_frame"}),
     ("handshake", "verdict", {"condition": "random"}),
     ("handshake", "verdict", {"condition": "bitflip_0.2"}),
     ("handshake", "verdict", {"condition": "bitflip_0.45"}),
     ("reply_to", "resolves", {"among": "1000"}),
     ("thread_turn", "recoverable", {"age": "3"}),
     ("thread_turn", "recoverable", {"age": "12"}),
     ("fidelity", "flags_corruption", {"p": "0.15"})])


def _how(q: Question) -> str:
    kv = " ".join(f"{k}={v}" for k, v in q[2].items())
    return (f"python3 agents/courier/claims.py measure {q[0]} {q[1]} {kv} "
            f"--seed <your seed>").replace("  ", " ")


def tell_all(seed: int = 2718) -> None:
    from knowledge import KB
    kb = KB()
    existing = {(c.subject, c.relation, tuple(sorted(c.context.items())))
                for c in kb.all_claims("courier")}
    for q in QUESTIONS:
        key = (q[0], q[1], tuple(sorted(q[2].items())))
        if key in existing:
            continue
        v = measure(q, seed)
        cid = kb.tell("courier", q[0], q[1], v, context=q[2] or None, how=_how(q))
        print(cid, q, "->", v)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "tell":
        tell_all()
    elif args and args[0] == "measure":
        seed = 2718
        if "--seed" in args:
            i = args.index("--seed")
            seed = int(args[i + 1])
            args = args[:i] + args[i + 2:]
        ctx = dict(a.split("=", 1) for a in args[3:])
        print(measure((args[1], args[2], ctx), seed))
    else:
        print(__doc__)
