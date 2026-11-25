"""reasoner's working step on the real channel + KB. Run once per work step:

    python3 reasoner/agent.py [--ask]        # --ask also poses new questions

1. load the shared KB (knowledge.py) into a FactMemory (conf = KB trust)
2. grade duty: reproduce every checkable fact I have not graded (never my own)
3. tell the module dependency graph of shared/*.py (check imports:...)
4. infer over trusted facts, tell new conclusions (check reason:...)
5. answer every question addressed to me on the channel, in the language
6. (--ask) pose questions to the others
Stateless: what is still unanswered is read off the channel (protocol.pending).
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT))

import language as L  # noqa: E402
import knowledge as K  # noqa: E402
import reason as R  # noqa: E402
import protocol as P  # noqa: E402

ME = "reasoner"


def build_fm(kb, min_trust=0.5):
    Rz = R.Reasoner()
    fm = R.FactMemory(Rz, min_trust=K.TRUST_ANSWER)
    for fid, s, r, o, t in kb.facts():
        if t >= min_trust:
            fm.add(s, r, o, conf=t)
    return Rz, fm


def grade_duty(kb):
    done = []
    for q in kb.ungraded(ME):
        if q["check"]:
            try:
                res = kb.reproduce(ME, q["fid"])
            except Exception as e:  # a checker that crashes decides nothing
                res = None
                print("  checker error", q["fid"], e)
            if res is not None:
                done.append((q["fid"], q["s"], q["r"], q["o"], res))
    return done


def dependency_facts():
    """(a.py depends_on b.py) for shared modules, read from the source."""
    shared = ROOT / "shared"
    mods = {p.stem for p in shared.glob("*.py")}
    out = []
    for p in sorted(shared.glob("*.py")):
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                names.add(n.module.split(".")[0])
        for m in sorted(names & mods - {p.stem}):
            out.append((p.name, "depends_on", m + ".py", f"imports:shared/{p.name}:{m}"))
    return out


def owner_facts():
    """(x.py owner agent) from each shared module's docstring '(owner: agent)'."""
    import re
    out = []
    for p in sorted((ROOT / "shared").glob("*.py")):
        m = re.search(r"owner: ([a-z]+)", p.read_text()[:600])
        if m:
            out.append((p.name, "owner", m.group(1), f"grep:shared/{p.name}:owner: {m.group(1)}"))
    return out


def tell_dependencies(kb):
    have = {q["fid"] for q in kb.query()}
    n = 0
    for s, r, o, chk in dependency_facts() + owner_facts():
        if K.fact_id(s, r, o) not in have:
            kb.tell(ME, s, r, o, check=chk)
            n += 1
    return n


def infer_and_tell(kb, fm):
    new = fm.infer(R.DEFAULT_RULES)
    have = {q["fid"] for q in kb.query()}
    fresh = [f for f in new if f.fid not in have and fm.conf(f) >= 0.5]
    fm.tell_kb(kb, fresh, agent=ME)
    return fresh


def answer_inbox(fm):
    """Answer every pending question to me/all through courier's serve():
    stateless (pending = asked and not yet answered by me, read off the
    channel), answers reply to the question id so distill() sees Q/A pairs."""
    def handler(q):
        if not isinstance(q, dict):
            return None
        return fm.answer(dict(q))
    sent = P.serve(ME, handler)
    return [(m.to, m.text()) for m in sent]


def grade_contradictions(kb, fm, strong=0.7):
    """A functional relation with two objects: if one side is well trusted
    and the other is not, grade the weaker one ok=False, how='contradicts'."""
    out = []
    for a, b in fm.contradictions():
        fb = kb.facts_.get(b.fid)
        if fb is None or fb["source"] == ME or ME in fb["grades"]:
            continue
        if kb.trust(a.fid) >= strong and kb.trust(b.fid) < strong:
            kb.grade(ME, b.fid, False, how="contradicts")
            out.append(((a.s, a.r, a.o), (b.s, b.r, b.o)))
    return out


def main(argv):
    kb = K.KB()
    print("KB:", kb.stats())
    g = grade_duty(kb)
    print(f"graded {len(g)} facts by reproducing their checks:")
    for fid, s, r, o, ok in g:
        print(f"   {'OK ' if ok else 'BAD'} {fid} ({s} {r} {o})")
    print("told dependency facts:", tell_dependencies(kb))
    Rz, fm = build_fm(kb)
    for a, b in grade_contradictions(kb, fm):
        print(f"graded BAD by contradiction: {b} vs trusted {a}")
    fresh = infer_and_tell(kb, fm)
    print(f"inferred and told {len(fresh)} new conclusions:")
    for f in fresh:
        print(f"   ({f.s} {f.r} {f.o}) conf={fm.conf(f):.2f} by {f.rule}")
    for who, a in answer_inbox(fm):
        print(f"answered {who}: {a}")


if __name__ == "__main__":
    main(sys.argv[1:])
