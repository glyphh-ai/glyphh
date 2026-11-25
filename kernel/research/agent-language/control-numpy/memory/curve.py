"""curve.py -- measure the group's learning curve on the shared KB.

World: a hidden set of true functional facts (s r -> o). Nobody reads the
truth directly. Each agent holds PRIVATE EVIDENCE: a random subset of true
facts it observed. Tellers tell what they (think they) saw; one teller is
noisy and corrupts a share of its tells. Graders grade a told fact only
when their OWN evidence covers (s, r): ok if it matches, bad if it
contradicts. That is "the world grades it": another agent's independent
observation, never the teller.

After every step we ask a fixed question set through kb.ask (the language
path) and score it against the hidden truth:
  correct / wrong / uncertain.
We compare two policies over the same event stream:
  graded : kb.ask (answers only from outside-graded, trusted facts)
  naive  : latest told object for (s, r), trust ignored
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import knowledge as K  # noqa: E402
import language as L  # noqa: E402

AGENTS = ["lexicon", "courier", "memory", "reasoner"]


def make_world(rng, n_subj=40, rels=("is_a", "lives_in", "color")):
    objs = {"is_a": [f"kind{i}" for i in range(8)],
            "lives_in": [f"place{i}" for i in range(8)],
            "color": [f"hue{i}" for i in range(8)]}
    truth = {}
    for i in range(n_subj):
        for r in rels:
            truth[(f"thing{i}", r)] = objs[r][rng.integers(len(objs[r]))]
    return truth, objs


def run(seed=0, steps=600, noisy="courier", noise=0.5, evidence=0.10,
        observe=0.5, grades_per_step=2, log_every=50, path=None,
        bad_grader=None, bad_mode="random"):
    """bad_grader: an agent that grades without looking. bad_mode "random"
    = coin-flip grades, "stamp" = rubber-stamps every fact ok."""
    rng = np.random.default_rng(seed)
    truth, objs = make_world(rng)
    keys = list(truth)
    ev = {a: set(k for k in keys if rng.random() < evidence) for a in AGENTS}
    questions = keys  # every (s, r) the world has
    tmp = path or Path(tempfile.mkdtemp()) / "kb.jsonl"
    lex = L.Lexicon(path=None)                       # private vocab: never pollute shared/
    kb = K.KB(tmp, lex=lex)                          # reputation-weighted view (default)
    flat = K.KB(tmp, lex=lex, weighted=False)        # same log, every grade counts 1
    naive = {}
    rows = []

    def score():
        out = {}
        for name, view in (("", kb), ("flat_", flat)):
            c = w = u = 0
            for (s, r) in questions:
                a = view.ask(s, r)
                if a.status == "uncertain":
                    u += 1
                elif a.obj == truth[(s, r)]:
                    c += 1
                else:
                    w += 1
            N = len(questions)
            out.update({name + "correct": c / N, name + "wrong": w / N,
                        name + "uncertain": u / N})
        nc = sum(1 for k in questions if naive.get(k) == truth[k])
        nu = sum(1 for k in questions if k not in naive)
        N = len(questions)
        out.update(naive_correct=nc / N, naive_uncertain=nu / N,
                   naive_wrong=(N - nc - nu) / N)
        return out

    for t in range(1, steps + 1):
        # the world keeps producing evidence: each agent may observe one more truth
        for a in AGENTS:
            if rng.random() < observe:
                ev[a].add(keys[rng.integers(len(keys))])
        teller = AGENTS[rng.integers(len(AGENTS))]
        pool = sorted(ev[teller]) or keys
        s, r = pool[rng.integers(len(pool))]
        o = truth[(s, r)]
        if teller == noisy and rng.random() < noise:
            o = [x for x in objs[r] if x != o][rng.integers(len(objs[r]) - 1)]
        kb.tell(teller, s, r, o)
        naive[(s, r)] = o
        # graders: other agents grade facts their own evidence covers
        for _ in range(grades_per_step):
            g = AGENTS[rng.integers(len(AGENTS))]
            if g == bad_grader:
                cand = kb.ungraded(g)                 # grades without evidence
            else:
                cand = [q for q in kb.ungraded(g) if (q["s"], q["r"]) in ev[g]]
            if not cand:
                continue
            q = cand[rng.integers(len(cand))]
            if g == bad_grader:
                ok = bool(rng.random() < 0.5) if bad_mode == "random" else True
            else:
                ok = q["o"] == truth[(q["s"], q["r"])]
            kb.grade(g, q["fid"], ok, how="observed")
        if t % log_every == 0:
            flat.refresh()
            rows.append({"step": t, **kb.stats(), **score()})
    return rows


def table(rows, title=""):
    print(title)
    print("step facts trusted | weighted: corr  wrong  unc  | flat: corr  wrong  unc  |"
          " naive: corr  wrong  unc")
    for r in rows:
        print(f"{r['step']:4d} {r['facts']:5d} {r['trusted']:7d} |"
              f"         {r['correct']:.3f} {r['wrong']:.3f} {r['uncertain']:.3f} |"
              f"     {r['flat_correct']:.3f} {r['flat_wrong']:.3f} {r['flat_uncertain']:.3f} |"
              f"      {r['naive_correct']:.3f} {r['naive_wrong']:.3f} {r['naive_uncertain']:.3f}")


def main():
    table(run(), "A. honest graders, courier tells 50% lies")
    table(run(bad_grader="lexicon", bad_mode="random"),
          "\nB. + lexicon grades by coin flip without evidence")
    table(run(bad_grader="lexicon", bad_mode="stamp"),
          "\nC. + lexicon rubber-stamps every fact ok")
    print("\nD. 5 seeds, final step (mean): weighted vs flat vs naive")
    for mode in (None, "random", "stamp"):
        fin = [run(seed=s, bad_grader=None if mode is None else "lexicon",
                   bad_mode=mode or "random", log_every=600)[-1] for s in range(5)]
        m = {k: np.mean([f[k] for f in fin]) for k in fin[0]}
        print(f"  bad_grader={str(mode):6s} weighted corr {m['correct']:.3f} wrong {m['wrong']:.3f}"
              f" unc {m['uncertain']:.3f} | flat corr {m['flat_correct']:.3f} wrong {m['flat_wrong']:.3f}"
              f" | naive corr {m['naive_correct']:.3f} wrong {m['naive_wrong']:.3f}")


if __name__ == "__main__":
    main()
