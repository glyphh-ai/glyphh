"""Where Ada's Security Incidents misses come from, against Jev's: each wrong action traced to its stage (the triage
disposition, close / queue / act, or the containment choice after both acted), each question's agreement with the
consensus (its zone, level or option), and a learning curve (Ada trained on part of each fold).

    uv run --project .. python diagnose.py            # dev, five folds
    BENCH_SET=test uv run --project .. python diagnose.py
"""

from __future__ import annotations

import os
import random
from collections import Counter

import ada
import run
import score
import security


def stage(case: dict, answers: dict) -> str:
    return security.disposition(answers, case)


def agreement(answers: dict[str, dict], reference: dict[str, dict], ids: list[str]) -> dict[str, tuple[int, int]]:
    """Per question: (agreeing, asked) over the cases both answered, each answer as its outcome (ada.label)."""
    out: dict[str, list[int]] = {}
    for cid in ids:
        mine, ref = answers.get(cid, {}), reference[cid]
        for q, a in mine.items():
            if q in ref:
                n = out.setdefault(q, [0, 0])
                n[0] += ada.label(q, a) == ada.label(q, ref[q])
                n[1] += 1
    return {q: (a, n) for q, (a, n) in out.items()}


def runs() -> tuple[dict, dict, dict, list[dict]]:
    labels = score.consensus_actions()
    cases = [c for c in run.cases() if c["id"] in labels]
    if run.SET == "test":
        dev = run.cases("dev")
        ref_dev = {c["id"]: run.consensus(c["id"], "dev") for c in dev}
        train = [c for c in dev if all(q in ref_dev[c["id"]] for q in ("is_true_positive", "context_explains_activity"))]
        out = ada.answer_cases(ada.train_model(train, ref_dev, ada.situation), cases, ada.situation)
    else:
        out = ada.answer_workflow(cases, ada.situation)
    return labels, out, run.load("jev"), cases


def curve(cases: list[dict], fractions=(0.25, 0.5, 0.75, 1.0)) -> None:
    """dev only: each fold's model trained on a random part of the other folds."""
    labels = score.consensus_actions()
    reference = {c["id"]: run.consensus(c["id"]) for c in cases}
    folds = [cases[i :: ada.FOLDS] for i in range(ada.FOLDS)]
    for f in fractions:
        right = n = 0
        for i, fold in enumerate(folds):
            train = [c for j, g in enumerate(folds) if j != i for c in g]
            train = random.Random(i).sample(train, round(len(train) * f))
            out = ada.answer_cases(ada.train_model(train, reference, ada.situation), fold, ada.situation)
            right += sum(out[c]["action"] == labels[c] for c in out)
            n += len(out)
        print(f"  trained on {f:4.0%} of the other folds (~{round(len(cases) * 0.8 * f)} cases): {right}/{n} {right / n:.1%}")


def main() -> None:
    labels, mine, jev, cases = runs()
    by_id = {c["id"]: c for c in cases}
    reference = {c["id"]: run.consensus(c["id"]) for c in cases}
    ids = [c["id"] for c in cases if c["id"] in mine and c["id"] in jev]
    print(f"{run.SET}: {len(ids)} cases")
    for name, got in (("ada", mine), ("jev", jev)):
        stages: Counter = Counter()
        for cid in ids:
            want = stage(by_id[cid], {q: reference[cid][q] for q in security.TRIAGE if q in reference[cid]})
            have = stage(by_id[cid], got[cid]["answers"])
            if got[cid]["action"] == labels[cid]:
                stages["right"] += 1
            elif want != have:
                stages[f"triage: {want} -> {have}"] += 1
            else:
                stages[f"after triage ({want}): wrong action"] += 1
        right = stages.pop("right")
        print(f"\n{name}: {right}/{len(ids)} right; misses by stage:")
        for k, v in stages.most_common():
            print(f"  {v:4d}  {k}")
    print("\nper question, agreement with the consensus (ada | jev, over the cases each was asked):")
    a = agreement({c: mine[c]["answers"] for c in ids}, reference, ids)
    j = agreement({c: jev[c]["answers"] for c in ids}, reference, ids)
    for q in (*security.TRIAGE, *security.CONTAINMENT):
        if q in a or q in j:
            fa = f"{a[q][0]:3d}/{a[q][1]:<3d} {a[q][0] / a[q][1]:5.1%}" if q in a else " " * 13
            fj = f"{j[q][0]:3d}/{j[q][1]:<3d} {j[q][0] / j[q][1]:5.1%}" if q in j else ""
            print(f"  {q:34s} {fa} | {fj}")
    if run.SET == "dev" and not os.environ.get("NO_CURVE"):
        print("\nlearning curve (dev, five folds):")
        curve(cases)


if __name__ == "__main__":
    main()
