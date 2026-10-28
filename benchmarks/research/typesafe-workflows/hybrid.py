"""Ada as the gate, Jev behind it, on Security Incidents: Ada answers the triage questions of every case (as ada.py
does: five folds on dev; trained on dev, once, on test); where its disposition is to act, Jev answers the
containment questions, and the same policy code (security.py) decides. Jev's containment answers are kept in
data/answers*/jev_containment.json (its own run's answers reused where it asked them already), so a rerun asks only
what is missing.

    TYPESAFE_API_KEY=... uv run --project .. python hybrid.py
    BENCH_SET=test TYPESAFE_API_KEY=... uv run --project .. python hybrid.py
"""

from __future__ import annotations

import time

import ada
import askers
import published
import run
import score
import security


def jev_containment(cases: list[dict], wanted: set[str]) -> dict[str, dict]:
    """Jev's answers to every containment question for each wanted case: its own run's where it has them all."""
    kept = run.load("jev_containment")
    own = run.load("jev")
    questions = published.questions("security_incidents")
    jev = None
    for c in cases:
        cid = c["id"]
        if cid not in wanted or cid in kept:
            continue
        mine = own.get(cid, {}).get("answers", {})
        if all(q in mine for q in security.CONTAINMENT):
            kept[cid] = {"answers": {q: mine[q] for q in security.CONTAINMENT}, "seconds": 0.0, "dollars": 0.0, "reused": True}
            continue
        jev = jev or askers.Jev()
        before, t0 = jev.spend.dollars(), time.time()
        answers = jev.ask(c["state"], {q: questions[q] for q in security.CONTAINMENT})
        kept[cid] = {"answers": answers, "seconds": time.time() - t0, "dollars": jev.spend.dollars() - before}
        run.save("jev_containment", kept)
        print(f"{cid}: Jev answered containment, ${kept[cid]['dollars']:.5f}", flush=True)
    run.save("jev_containment", kept)
    return kept


def blend(cases: list[dict], alone: dict, jev_alone: dict, jev_contained: dict) -> dict[str, str]:
    """Both read the triage: P(true positive) the mean of Ada's and Jev's (each errs its own way: Ada acts too
    often, Jev too seldom), the context and evidence answers Jev's; where that acts, Jev's containment answers. A
    case Ada did not act on and Jev did not act on cannot act here (the mean is above 0.75 only when one is), so
    every acting case has Jev's containment answers already."""
    out = {}
    for c in cases:
        cid = c["id"]
        mine, theirs = alone[cid]["answers"], jev_alone[cid]["answers"]
        triage = {
            "is_true_positive": (mine["is_true_positive"] + theirs["is_true_positive"]) / 2,
            "context_explains_activity": theirs["context_explains_activity"],
            "evidence_strength": theirs["evidence_strength"],
        }
        contained = jev_contained.get(cid, {}).get("answers") or {q: theirs[q] for q in security.CONTAINMENT if q in theirs}
        out[cid], _ = security.decide(lambda qs, t=triage, k=contained: {q: t[q] if q in t else k[q] for q in qs}, c)
    return out


def main() -> None:
    labels = score.consensus_actions()
    cases = [c for c in run.cases() if c["id"] in labels]
    if run.SET == "test":
        dev = run.cases("dev")
        ref = {c["id"]: run.consensus(c["id"], "dev") for c in dev}
        train = [c for c in dev if all(q in ref[c["id"]] for q in ("is_true_positive", "context_explains_activity"))]
        alone = ada.answer_cases(ada.train_model(train, ref, ada.situation), cases, ada.situation)
    else:
        alone = ada.answer_workflow(cases, ada.situation)
    by_id = {c["id"]: c for c in cases}
    acting = {cid for cid, o in alone.items() if security.disposition(o["answers"], by_id[cid]) == "act"}
    jev = jev_containment(cases, acting)
    hybrid = {}
    for cid, o in alone.items():
        if cid in acting:
            answers = {**{q: o["answers"][q] for q in security.TRIAGE}, **jev[cid]["answers"]}
            hybrid[cid] = security.containment_action(answers, by_id[cid])
        else:
            hybrid[cid] = o["action"]
    jev_alone = run.load("jev")
    blended = blend(cases, alone, jev_alone, jev)
    n = len(alone)
    rows = (
        ("Jev alone", sum(jev_alone[c]["action"] == labels[c] for c in alone)),
        ("Ada alone", sum(o["action"] == labels[c] for c, o in alone.items())),
        ("Ada gate + Jev containment", sum(hybrid[c] == labels[c] for c in alone)),
        ("Ada+Jev triage, Jev contain", sum(blended[c] == labels[c] for c in blended)),
    )
    print(f"\n{run.SET}: {n} cases; Ada acts on {len(acting)}, Jev asked there ({sum(not jev[c].get('reused') for c in acting)} new)")
    for name, right in rows:
        print(f"  {name:28s} {right:4d}/{n} {right / n:6.1%}")
    spent = sum(jev[c]["dollars"] for c in acting)
    print(f"  Jev's containment calls: ${spent:.4f} for this set")


if __name__ == "__main__":
    main()
