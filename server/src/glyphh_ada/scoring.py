"""A backtest's numbers for one candidate over the held-out cases (backtest.py), and each candidate's change against
the active version."""

import math
from collections import defaultdict
from typing import Any

import glyphh_spec

BINS: int = 10  # of confidence, for the calibration error
FLOOR: float = 1e-6  # the least probability log-loss counts
DELTAS: tuple[str, ...] = ("accuracy", "top_accuracy", "log_loss", "ask_rate", "calibration_error", "cost_mean")


class Scores:
    def __init__(self, costs: glyphh_spec.Output) -> None:
        self.costs, self.priced = costs, bool(costs.costs)
        self.n = self.right = self.top_right = self.asked = self.answered_right = self.sufficient = 0
        self.loss = self.cost = 0.0
        self.bins: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(BINS)]  # confidence, right, count
        self.mistakes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def add(self, decided: dict[str, Any], voted: Any, truth: str) -> None:
        outcome, probabilities = decided["outcome"], decided["probabilities"]
        right = outcome == truth
        self.n += 1
        self.right += right
        self.top_right += voted.top == truth
        self.sufficient += bool(voted.sufficient)
        self.loss -= math.log(max(probabilities.get(truth, 0.0), FLOOR))
        if decided["ask"]:
            self.asked += 1
        else:
            self.answered_right += right
        self.cost += self.costs.cost(outcome, truth) if outcome is not None else 0.0  # nothing known: it asks
        confidence = max(probabilities.values(), default=0.0)
        held = self.bins[min(int(confidence * BINS), BINS - 1)]
        held[0], held[1], held[2] = held[0] + confidence, held[1] + right, held[2] + 1
        if not right:
            self.mistakes[truth][str(outcome)] += 1

    def result(self) -> dict[str, Any]:
        n = max(self.n, 1)
        answered = self.n - self.asked
        out: dict[str, Any] = {
            "n": self.n,
            "accuracy": round(self.right / n, 4),
            "top_accuracy": round(self.top_right / n, 4),
            "log_loss": round(self.loss / n, 4),
            "ask_rate": round(self.asked / n, 4),
            "accuracy_answered": round(self.answered_right / answered, 4) if answered else None,
            "coverage": round(self.sufficient / n, 4),
            "calibration_error": round(sum(abs(c - r) for c, r, _ in self.bins) / n, 4),
            "mistakes": {t: dict(d) for t, d in self.mistakes.items()},
        }
        if self.priced:
            out["cost"] = round(self.cost, 4)
            out["cost_mean"] = round(self.cost / n, 4)
        return out


def compare(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The active version's numbers, and each candidate's with its change against them."""
    active, candidates = results[0], results[1:]
    for c in candidates:
        if "error" not in c and "error" not in active:
            c["change"] = {k: round(c[k] - active[k], 4) for k in DELTAS if k in c and k in active}
    return {"active": active, "candidates": candidates}
