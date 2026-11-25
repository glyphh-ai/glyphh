"""Ada's typed outputs (kernel 3.15.0) on Security Incidents, against Jev: the same model as ada.py with each
question given a kind the kernel now has, scored the same way (the consensus action; five folds on dev, trained on
dev and answered once on test).

    base         ada.py as it is: every question a flat choice (a noul's zones, a score's levels)
    score        a noul's zones and a score's levels as kind "score": ordered, a mistake costs the levels it is off
    number       a noul as kind "number" (0 to 1, step 0.05) learned from the consensus's own P(true), not its zone;
                 the answer is the least-cost bin's midpoint
    number-mean  the same, the answer the expected value
    union        the containment questions hang on triage: `when` is_true_positive is above 0.75 (zones z3, z4)
    score+union

    uv run --project .. python typed_outputs.py [variant ...]
"""

from __future__ import annotations

import sys
import time

import ada
import run
import score
import security

VARIANTS = ("base", "score", "number", "number-mean", "union", "score+union")
STEP = 0.05


def kinded_spec(parts: set[str]):
    import published

    plain = ada.spec

    def spec() -> dict:
        s = plain()
        questions = published.questions("security_incidents")
        for q, o in s["outputs"].items():
            kind = questions[q]["type"]
            if "number" in parts and kind == "noul":
                s["outputs"][q] = {"kind": "number", "number": {"min": 0, "max": 1, "step": STEP}}
            elif "score" in parts and kind in ("noul", "score"):
                o["kind"] = "score"
            if "union" in parts and q in security.CONTAINMENT:
                s["outputs"][q]["when"] = {"output": "is_true_positive", "in": ["z3", "z4"]}
        return s

    return spec


def kinded_graded(parts: set[str]):
    plain = ada.graded

    def graded(c: dict, reference: dict[str, dict]) -> dict:
        out = plain(c, reference)
        if "number" in parts:
            for q in ada.CUTS:
                if q in reference[c["id"]]:
                    out[q] = reference[c["id"]][q]  # the consensus's P(true), the number itself
        return out

    return graded


def kinded_answers(parts: set[str]):
    def answer_cases(trained: dict, cases: list[dict], situation) -> dict[str, dict]:
        model, base, questions = trained["model"], trained["base"], trained["questions"]

        def answer(qs, data):
            decided = model.decide_all(data, outputs=list(qs))
            out = {}
            for q in qs:
                d = decided[q]
                if "number" in parts and q in ada.CUTS:
                    if d["outcome"] is None:
                        out[q] = 0.5
                    else:
                        out[q] = d["value"] if "mean" in parts else float(d["outcome"])
                    continue
                outcome = d["outcome"] or max(base[q], key=base[q].get)
                if questions[q]["type"] == "noul":
                    out[q] = ada.zones(q)[outcome]
                else:
                    out[q] = {o: float(o == outcome) for o in ada.options(q, questions[q])}
            return out

        res = {}
        for c in cases:
            t0 = time.time()
            data = situation(c)
            action, answers = security.decide(lambda qs, data=data: answer(qs, data), c)
            res[c["id"]] = {"action": action, "answers": answers, "seconds": time.time() - t0, "dollars": 0.0}
        return res

    return answer_cases


def evaluate(variant: str) -> tuple[int, int, float]:
    parts = set(variant.replace("number-mean", "number+mean").split("+"))
    ada.spec = kinded_spec(parts)
    ada.graded = kinded_graded(parts)
    ada.answer_cases = kinded_answers(parts)
    labels = score.consensus_actions()
    cases = [c for c in run.cases() if c["id"] in labels]
    if run.SET == "test":
        dev = run.cases("dev")
        reference = {c["id"]: run.consensus(c["id"], "dev") for c in dev}
        train = [c for c in dev if all(q in reference[c["id"]] for q in ("is_true_positive", "context_explains_activity"))]
        out = ada.answer_cases(ada.train_model(train, reference, ada.situation), cases, ada.situation)
    else:
        out = ada.answer_workflow(cases, ada.situation)
    right = sum(out[c]["action"] == labels[c] for c in out)
    return right, len(out), sum(o["seconds"] for o in out.values()) / len(out)


if __name__ == "__main__":
    plain = (ada.spec, ada.graded, ada.answer_cases)
    for v in sys.argv[1:] or VARIANTS:
        ada.spec, ada.graded, ada.answer_cases = plain
        right, n, seconds = evaluate(v)
        print(f"{run.SET:4s} {v:12s} {right:4d}/{n:<4d} {right / n:6.1%} {seconds:7.3f} s/case", flush=True)
