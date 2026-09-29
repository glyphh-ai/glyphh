"""courier/bench.py -- measure the protocol.  python3 courier/bench.py
All runs use a PRIVATE Lexicon(path=None): nothing is written to shared/vocab.txt."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
import language as L  # noqa: E402
import protocol as P  # noqa: E402

AG = ["lexicon", "courier", "memory", "reasoner"]
ACTS = ["assert", "ask", "answer", "propose", "agree", "disagree", "tell"]


def world(n_words=200, seed=0):
    lex = L.Lexicon(path=None)
    words = [f"w{i}" for i in range(n_words)]
    rels = [f"r{i}" for i in range(20)]
    lex.learn(words + rels, persist=False)
    return lex, words, rels, np.random.default_rng(seed)


def rand_msg(lex, words, rels, rng, parent=None):
    s, o = rng.choice(words, 2, replace=False)
    content = {"act": "fact", "subj": str(s), "rel": str(rng.choice(rels)), "obj": str(o)}
    a, b = rng.choice(AG, 2, replace=False)
    return P.compose(str(a), str(b), str(rng.choice(ACTS)), content, re=parent,
                     thread=parent, conf=str(rng.choice(P.CONFS)), lex=lex)


def same(m, d):
    return (d.content is not None and d.act == m.act and d.sender == m.sender and d.to == m.to and d.conf == m.conf
            and L.canonical(d.content) == L.canonical(m.content) and d.re == m.re)


def roundtrip(n=300, n_ids=1000):
    lex, W, R, rng = world()
    ids = [f"m{rng.integers(1 << 48):012x}" for _ in range(n_ids)]
    ok = 0
    for _ in range(n):
        par = str(rng.choice(ids))
        m = rand_msg(lex, W, R, rng, parent=par)
        d = P.decode(P.wire(m), known_ids=ids, lex=lex)
        ok += same(m, d) and d.status == "ok"
    return ok / n


def noise_curve(ps=(0, .02, .05, .1, .15, .2, .25, .3, .35, .4), n=100):
    lex, W, R, rng = world(seed=1)
    ids = [f"m{rng.integers(1 << 48):012x}" for _ in range(100)]
    rows = []
    for p in ps:
        exact = 0; err = []; st = {}
        for _ in range(n):
            m = rand_msg(lex, W, R, rng, parent=str(rng.choice(ids)))
            d = P.decode(P.noisy(P.wire(m), p, rng), known_ids=ids, lex=lex)
            exact += same(m, d)
            st[d.status] = st.get(d.status, 0) + 1
            if d.status in ("ok", "noisy"):
                err.append(abs(d.flip_est - p))
        rows.append((p, exact / n, float(np.mean(err)) if err else None, st))
    return rows


def foreign(n=200):
    """Random bytes, all-zero, an 'other language' (same algebra, other codebook =
    a fixed secret permutation of every vector), and bare meanings."""
    lex, W, R, rng = world(seed=2)
    perm = np.random.default_rng(99).permutation(L.D)
    out = {"random": {}, "zeros": {}, "other_language": {}, "bare_meaning": {}, "text_bytes": {}}
    for _ in range(n):
        m = rand_msg(lex, W, R, rng)
        cases = {
            "random": rng.integers(0, 256, L.D // 8).astype(np.uint8),
            "zeros": np.zeros(L.D // 8, np.uint8),
            "other_language": L.to_wire(m.vector[perm]),
            "bare_meaning": L.to_wire(L.encode(m.content, lex, persist=False)),
            "text_bytes": np.frombuffer((m.text() * 20).encode()[:L.D // 8], np.uint8),
        }
        for k, pl in cases.items():
            s = P.decode(pl, lex=lex).status
            out[k][s] = out[k].get(s, 0) + 1
    return out


def capacity(sizes=(1, 4, 8, 12, 16, 20, 24), n=30):
    """Content = a list of k facts (3 leaves each) inside the envelope."""
    lex, W, R, rng = world(seed=3)
    rows = []
    for k in sizes:
        ok = 0
        for _ in range(n):
            facts = [{"subj": str(a), "rel": str(rng.choice(R)), "obj": str(b)}
                     for a, b in (rng.choice(W, 2, replace=False) for _ in range(k))]
            m = P.compose("memory", "all", "tell", facts, lex=lex)
            d = P.decode(P.wire(m), lex=lex)
            ok += d.content is not None and L.canonical(d.content) == L.canonical(facts) and d.status == "ok"
        rows.append((k, ok / n))
    return rows


def thread_turns(lengths=(4, 8, 16, 32), n=10):
    lex, W, R, rng = world(seed=4)
    rows = []
    for T in lengths:
        hit = 0
        for _ in range(n):
            msgs = [rand_msg(lex, W, R, rng)]
            for _ in range(T - 1):
                msgs.append(rand_msg(lex, W, R, rng, parent=msgs[-1].id))
            th = P.Thread(msgs)
            tv = th.vector()
            hit += sum(th.turn(tv, i)[0] is m for i, m in enumerate(msgs))
        rows.append((T, hit / (n * T)))
    return rows


def routing(n_q=200, per_agent=20, topic=10):
    """Each agent 'owns' a topic (a set of subjects). Profiles are built from what
    they asserted; route fresh questions about a topic's subject (never seen with
    that relation) and check the owner comes first."""
    lex, W, R, rng = world(seed=5)
    topics = {a: [str(w) for w in W[i * topic:(i + 1) * topic]] for i, a in enumerate(AG)}
    msgs = []
    for a, subs in topics.items():
        for _ in range(per_agent):
            c = {"act": "fact", "subj": str(rng.choice(subs)), "rel": str(rng.choice(R)),
                 "obj": str(rng.choice(W))}
            msgs.append(P.compose(a, "all", "assert", c, lex=lex))
    profs = P.profiles(msgs)
    hit = 0
    for _ in range(n_q):
        a = str(rng.choice(AG))
        q = {"act": "query", "subj": str(rng.choice(topics[a])), "rel": str(rng.choice(R)), "obj": "?"}
        hit += P.route(q, profs)[0][0] == a
    return hit / n_q


def long_content(sizes=(5, 20, 40, 100), n=10):
    """Lists of k facts sent as multi-part messages, decoded in random order."""
    lex, W, R, rng = world(seed=6)
    rows = []
    for k in sizes:
        ok = 0
        for _ in range(n):
            items = [{"subj": str(a), "rel": str(rng.choice(R)), "obj": str(b)}
                     for a, b in (rng.choice(W, 2, replace=False) for _ in range(k))]
            parts = P.compose_parts("memory", "all", "tell", items, lex=lex)
            ids = [p.id for p in parts]
            dec = [P.decode(P.wire(parts[i]), known_ids=ids, lex=lex) for i in rng.permutation(len(parts))]
            got = P.reassemble(dec, parts[0].id, lex=lex)
            ok += got is not None and L.canonical(got) == L.canonical(items)
        rows.append((k, len(parts), ok / n))
    return rows


if __name__ == "__main__":
    print(f"roundtrip exact (all fields + re among 1000 ids): {roundtrip():.3f}")
    print("noise curve  p  exact  |flip_est-p|  statuses")
    for p, ex, e, st in noise_curve():
        print(f"  {p:.2f}  {ex:.2f}  {e if e is None else round(e, 4)}  {st}")
    print("foreign/garbage detection:", foreign())
    print("capacity (k facts in one message -> exact):", capacity())
    print("thread vector turn recovery (len -> acc):", thread_turns())
    print("multi-part (k facts -> parts, exact after random-order reassembly):", long_content())
    print(f"routing accuracy (4 agents, chance 0.25): {routing():.3f}")
