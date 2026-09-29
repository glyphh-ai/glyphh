"""The REAL learning curve: replay the group's own ledger (shared/kb).

Takes every tell and grade the four agents actually made, in time
order, into a fresh temp KB, and at checkpoints asks every question the
group has ever raised. Reports, per checkpoint, how many questions the
group could answer by reflex (known) versus would have to consult.

    python3 agents/memory/replay.py [--points 12]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "shared"))

from knowledge import KB  # noqa: E402


def replay(src: KB, points: int = 12):
    claims = src.db.execute(
        "SELECT ts, 'tell', id, author, situation, value, evidence FROM claims"
    ).fetchall()
    grades = src.db.execute(
        "SELECT ts, 'grade', claim_id, grader, ok, how, '' FROM grades"
    ).fetchall()
    events = sorted(claims + grades, key=lambda e: e[0])
    questions = sorted({c[4] for c in claims})
    dst = KB(tempfile.mkdtemp(prefix="kbreplay-"),
             veto_rule=src.veto_rule)
    t0 = events[0][0]
    marks = {int(round(i * (len(events) - 1) / (points - 1)))
             for i in range(points)}
    rows = []
    for i, (ts, kind, a, b, c, d, e) in enumerate(events):
        if kind == "tell":
            sit = json.loads(c)
            subj, rel = sit.pop("subject"), sit.pop("relation")
            dst.tell(b, subj, rel, d, context=sit, cid=a,
                     evidence=json.loads(e))
        else:
            dst.grade(b, a, bool(c), d)
        if i in marks:
            st = [dst.ask_situation(json.loads(q), log=False).status
                  for q in questions]
            raised = sum(1 for s in st if s != "unknown")
            rows.append({
                "t_min": round((ts - t0) / 60, 1), "events": i + 1,
                "questions_raised": raised,
                "known": st.count("known"),
                "known_frac_of_raised": round(st.count("known") / raised, 3),
                "consult_frac_of_raised": round(1 - st.count("known") / raised, 3),
                "vetoed": st.count("vetoed"),
            })
    dst.close()
    return rows


if __name__ == "__main__":
    pts = int(sys.argv[sys.argv.index("--points") + 1]) if "--points" in sys.argv else 12
    kb = KB()
    rows = replay(kb, pts)
    hdr = list(rows[0])
    print(" | ".join(hdr))
    for r in rows:
        print(" | ".join(str(r[h]) for h in hdr))
