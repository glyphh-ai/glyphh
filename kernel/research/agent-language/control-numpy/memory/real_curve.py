"""real_curve.py -- the learning curve of the REAL group KB (shared/kb.jsonl).

Replays the shared log event by event into a private copy (read-only on
shared/) and, after every k events, asks every (subj, rel) the group has
ever told. For each answer we re-run the answering fact's check (if it has
one) to see whether the answer is reproducibly right:
    right    answered, check re-runs True
    wrong    answered, check re-runs False
    unchk    answered, fact has no check (trusted by observation only)
    uncertain
Run: python3 memory/real_curve.py [k]
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
import knowledge as K  # noqa: E402
import language as L  # noqa: E402
try:  # plug in the other agents' checkers so their checks can be re-run
    import protocol  # noqa: F401,E402
    import reason  # noqa: F401,E402
except Exception:
    pass


def rerun(kb, fid):
    chk = kb.facts_[fid].get("check")
    if not chk:
        return None
    fn = K._checker(chk.split(":", 1)[0])
    if fn is None:
        return None
    try:
        return fn(kb, chk, fid)
    except TypeError:
        return fn(kb, chk)


def main(k=5):
    lines = [l for l in K.DEFAULT_LOG.read_text().splitlines() if l.strip()]
    lex = L.Lexicon()                       # reads shared vocab; we never tell/grade, so no writes
    full = K.KB(K.DEFAULT_LOG, lex=lex)
    questions = sorted({(f["s"], f["r"]) for f in full.facts_.values()})
    verdict = {fid: rerun(full, fid) for fid in full.facts_}
    tmp = Path(tempfile.mkdtemp()) / "kb.jsonl"
    print(f"{len(lines)} events, {len(questions)} questions, "
          f"{sum(v is not None for v in verdict.values())} facts re-runnable")
    print(" events facts graded | answered right wrong unchk | uncertain | uncertain_now")
    rows = []
    for n in list(range(k, len(lines), k)) + [len(lines)]:
        tmp.write_text("\n".join(lines[:n]) + "\n")
        kb = K.KB(tmp, lex=lex)
        right = wrong = unchk = unc = 0
        for s, r in questions:
            a = kb.ask(s, r)
            if a.status == "uncertain":
                unc += 1
            elif verdict.get(a.fid) is True:
                right += 1
            elif verdict.get(a.fid) is False:
                wrong += 1
            else:
                unchk += 1
        st = kb.stats()
        Q = len(questions)
        now = {(f["s"], f["r"]) for f in kb.facts_.values()}
        unc_now = sum(1 for q in now if kb.ask(*q).status == "uncertain") / max(1, len(now))
        rows.append((n, st["facts"], st["graded"], right, wrong, unchk, unc))
        print(f"{n:7d} {st['facts']:5d} {st['graded']:6d} |   {(Q-unc)/Q:.3f}  {right:4d} {wrong:4d}"
              f"  {unchk:4d} | {unc/Q:.3f}     | {unc_now:.3f}")
    return rows


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
