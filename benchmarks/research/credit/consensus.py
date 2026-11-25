"""TypeSafe's measurement on our 200: accuracy against a consensus of two frontier models, beside accuracy against
what really happened.

TypeSafe's workflow evals (evals.typesafe.ai) have no real outcomes: the reference is the average of two
high-reasoning frontier models' predictions, and every contestant is scored by how often it agrees. Here the two
references are Claude Fable 5.1 and Claude Opus 5.5 (theirs: GPT-6 Astra and Fable 5.1), each giving P(bad) for the
200 after reading the 800 (`results/ref_*.json`). The consensus label is "bad" when their mean P(bad) > 0.5.

    uv run python benchmarks/credit/consensus.py

Scores every answers file in results/ ({id: "good"|"bad"}) both ways.
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
REFS = ("ref_fable", "ref_opus")
SKIP = {"holdout_labels", *REFS}


def agree(a: dict[str, str], b: dict[str, str]) -> float:
    return sum(a.get(i) == v for i, v in b.items()) / len(b)


def main() -> None:
    truth = json.loads((RESULTS / "holdout_labels.json").read_text())
    refs = {r: json.loads((RESULTS / f"{r}.json").read_text()) for r in REFS}
    for r, p in refs.items():
        if set(p) != set(truth):
            raise SystemExit(f"{r} does not cover the 200")
    mean = {i: sum(p[i] for p in refs.values()) / len(refs) for i in truth}
    consensus = {i: "bad" if m > 0.5 else "good" for i, m in mean.items()}
    labels = {r: {i: "bad" if v > 0.5 else "good" for i, v in p.items()} for r, p in refs.items()}

    print(
        f"consensus: {sum(v == 'bad' for v in consensus.values())} of 200 bad; real outcomes: "
        f"{sum(v == 'bad' for v in truth.values())} bad"
    )
    print(f"consensus vs real outcomes: {agree(consensus, truth):.1%}")
    for r, lab in labels.items():
        print(f"{r} alone: {agree(lab, truth):.1%} vs real outcomes, {agree(lab, consensus):.1%} vs consensus")
    print()
    print(f"{'answers':45s} {'vs real outcome':>16s} {'vs consensus':>13s}")
    for f in sorted(RESULTS.glob("*.json")):
        if f.stem in SKIP or f.stem.endswith("_raw"):
            continue
        answers = json.loads(f.read_text())
        print(f"{f.stem:45s} {agree(answers, truth):16.1%} {agree(answers, consensus):13.1%}")


if __name__ == "__main__":
    main()
