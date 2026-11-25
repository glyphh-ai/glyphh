"""Measurements for the protocol. Run: python3 courier/measure.py

Every number in courier/REPORT.md comes from this script's output.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import protocol as P  # noqa: E402
from language import Lexicon  # noqa: E402

LX = Lexicon(path=None, author="measure")   # private: never touches the shared codebook

rng = np.random.default_rng(0)
FOREIGN = {s: Lexicon(path=None, seed=s) for s in (7, 1234)}
AG = ["lexicon", "courier", "memory", "reasoner"]
VOCAB = [f"word{i}" for i in range(200)]
ROLES = [f"r{i}" for i in range(12)]


def rand_content(n_roles):
    roles = rng.choice(ROLES, n_roles, replace=False)
    return {r: str(rng.choice(VOCAB)) for r in roles}


def rand_msg(n_roles=3, reply=None, thread=None):
    parts = rand_content(n_roles)
    m = P.Message(str(rng.choice(AG)), str(rng.choice(AG + ["all"])),
                  str(rng.choice(P.ACTS)), parts,
                  reply_to=reply, thread=thread)
    return m, parts


def G(m, lx=None):
    return m.glyph(lx or LX)


def envelope_accuracy(trials=150):
    print("\n## 1. Field decode accuracy from the glyph alone "
          f"(vocab={len(VOCAB)} words, {len(ROLES)} candidate roles)")
    print("content_roles | envelope | from/to/act field acc | all 3 right "
          "| content exact | content recall | false content roles")
    for n_roles in (1, 2, 3, 4, 6, 8):
        for with_links in (False, True):
            env_ok = fld_ok = 0
            c_exact = c_recall = c_false = 0.0
            for _ in range(trials):
                reply = LX.encode(rand_content(3)) if with_links else None
                thread = P.Conversation([reply]).state() if with_links else None
                m, parts = rand_msg(n_roles, reply, thread)
                d = P.decode(G(m), LX, depth=0)
                ok = [d.get("from") == m.sender, d.get("to") == m.to,
                      d.get("act") == m.act]
                fld_ok += sum(ok)
                env_ok += all(ok)
                got = d.content if isinstance(d.content, dict) else {}
                c_exact += got == parts
                c_recall += sum(got.get(r) == w for r, w in parts.items()) / len(parts)
                c_false += len(set(got) - set(parts))
            print(f"{n_roles:>13} | {'links' if with_links else 'plain':>8} "
                  f"| {fld_ok / (3 * trials):.3f} | {env_ok / trials:.3f} | {c_exact / trials:.3f} "
                  f"| {c_recall / trials:.3f} | {c_false / trials:.2f}/msg")


def noise(trials=300):
    print("\n## 2. Validity: handshake sim under corruption / foreign seed")
    print("condition | mean proto_sim | accepted rate")
    rows = []
    for p in (0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5):
        sims, acc = [], 0
        for _ in range(trials):
            m, _ = rand_msg(3)
            g = G(m).copy()
            flip = rng.random(P.DIM) < p
            g[flip] *= -1
            d = P.decode(g, LX, read_content=False)
            sims.append(d.proto_sim)
            acc += d.valid
        rows.append((f"bitflip p={p:.2f}", np.mean(sims), acc / trials))
    for seed in (7, 1234):
        sims, acc = [], 0
        for _ in range(trials):
            m, parts = rand_msg(3)
            d = P.decode(G(m, FOREIGN[seed]), LX, read_content=False)
            sims.append(d.proto_sim)
            acc += d.valid
        rows.append((f"foreign seed={seed}", np.mean(sims), acc / trials))
    sims, acc = [], 0
    for _ in range(trials):
        d = P.decode((rng.integers(0, 2, P.DIM) * 2 - 1).astype(np.int8), LX, read_content=False)
        sims.append(d.proto_sim)
        acc += d.valid
    rows.append(("random glyph", np.mean(sims), acc / trials))
    sims, acc = [], 0
    for _ in range(trials):   # a bare content thought posted without envelope
        d = P.decode(LX.encode(rand_content(3)), LX, read_content=False)
        sims.append(d.proto_sim)
        acc += d.valid
    rows.append(("bare thought (no envelope)", np.mean(sims), acc / trials))
    for name, s, a in rows:
        print(f"{name:>28} | {s:+.3f} | {a:.3f}")


def reply_resolution(trials=100):
    print("\n## 3. reply_to resolution: pick the parent among N seen messages")
    print("N seen | accuracy | mean sim(parent) | mean best wrong sim")
    for N in (10, 100, 1000):
        ok, ps, ws = 0, [], []
        for _ in range(trials):
            seen = {f"m{i}": G(rand_msg(3)[0]) for i in range(N)}
            pid = f"m{rng.integers(N)}"
            child, _ = rand_msg(3, reply=seen[pid])
            d = P.decode(G(child), LX, known_msgs=seen, read_content=False)
            ok += d.get("reply_to") == pid
            u = P.roll(P.bind(G(child), LX.role("reply_to")), -1)
            s = {k: P.sim(u, v) for k, v in seen.items()}
            ps.append(s.pop(pid))
            ws.append(max(s.values()))
        print(f"{N:>6} | {ok / trials:.3f} | {np.mean(ps):.3f} | {np.mean(ws):.3f}")


def thread_depth(trials=200, length=24):
    print(f"\n## 4. How long can a thread get? Conversation.state() of {length} turns;"
          " identify turn at age a among the thread's own turns + 100 others")
    print("age | top-1 accuracy | mean sim(turn) | noise floor (best other)")
    acc = np.zeros(length)
    sims = np.zeros(length)
    floor = np.zeros(length)
    for _ in range(trials):
        turns = [G(rand_msg(3)[0]) for _ in range(length)]
        others = [G(rand_msg(3)[0]) for _ in range(100)]
        conv = P.Conversation(turns)
        st = conv.state()
        pool = turns + others
        M = np.stack(pool).astype(np.float32)
        for age in range(length):
            probe = P.roll(st, -age).astype(np.float32)
            s = (M @ probe) / P.DIM
            target = length - 1 - age
            acc[age] += int(np.argmax(s)) == target
            sims[age] += s[target]
            floor[age] += np.max(np.delete(s, target))
    for age in range(length):
        if age < 10 or age % 4 == 3:
            print(f"{age:>3} | {acc[age] / trials:.3f} | {sims[age] / trials:+.3f}"
                  f" | {floor[age] / trials:+.3f}")


def thread_recognition(trials=200):
    print("\n## 5. Thread recognition: which of K conversations does a new "
          "message belong to (via its thread field)?")
    print("K threads | accuracy")
    for K in (5, 20, 100):
        ok = 0
        for _ in range(trials):
            threads = {}
            for k in range(K):
                c = P.Conversation([G(rand_msg(3)[0])
                                    for _ in range(int(rng.integers(2, 8)))])
                threads[f"t{k}"] = c.state()
            tid = f"t{rng.integers(K)}"
            m, _ = rand_msg(3, thread=threads[tid])
            d = P.decode(G(m), LX, known_threads=threads, read_content=False)
            ok += d.get("thread") == tid
        print(f"{K:>9} | {ok / trials:.3f}")


def conversation_as_content(trials=200):
    print("\n## 6. A conversation as the CONTENT of a message: can the receiver"
          " still tell which conversation (among 20) was summarized?")
    ok = 0
    for _ in range(trials):
        convs = {f"c{k}": P.Conversation([G(rand_msg(3)[0]) for _ in range(5)]).state()
                 for k in range(20)}
        cid = f"c{rng.integers(20)}"
        m = P.Message("courier", "all", "tell", convs[cid])
        d = P.decode(G(m), LX, read_content=False)
        name, s, _ = P.cleanup(d.content_glyph, convs)
        ok += name == cid
    print(f"accuracy {ok / trials:.3f}")


if __name__ == "__main__":
    only = sys.argv[1:]
    for name, fn in [("1", envelope_accuracy), ("2", noise), ("3", reply_resolution),
                     ("4", thread_depth), ("5", thread_recognition),
                     ("6", conversation_as_content)]:
        if not only or name in only:
            fn()
    sys.exit(0)
    envelope_accuracy()
    noise()
    reply_resolution()
    thread_depth()
    thread_recognition()
    conversation_as_content()
