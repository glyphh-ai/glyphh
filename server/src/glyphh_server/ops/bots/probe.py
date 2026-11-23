"""A decision probed for what it holds no class of (docs/specs/bots.md, 9): the Resume Screener's `made` decision
holds only generated applications (some, mostly, fully), so an application written by a person is one with no close
generated precedent. When the decision is seeded (`probe` true; ops/bots/seeds.py), its nearest precedent's
similarity (its own, on Ada's receipts) is measured over the seed set's test applicants, never recorded, and kept in
the runner's state as the reference (p5 to p95). `decide` (ops/bots/agent/ada.py) then decides only the items whose
nearest precedent is at least as close as the reference's p5; the rest it answers human, and never asks about."""

import json
import math
from typing import Any

KEY: str = "_glyphh_probe:"
CUTS: tuple[int, ...] = (5, 25, 50, 75, 95)
FLOOR: str = "p5"


def nearest(model: Any, case: dict[str, Any]) -> float | None:
    """The similarity of the decision's nearest precedent to the case (None: it holds none)."""
    receipts = getattr(model.decide(case), "receipts", None) or []
    sims = [float(r["sim"]) for r in receipts if isinstance(r, dict) and isinstance(r.get("sim"), int | float)]
    return max(sims) if sims else None


def spread(sims: list[float]) -> dict[str, Any]:
    """The p5 to p95 of the similarities (nearest rank), and how many they were."""
    ranked = sorted(sims)
    cut = {f"p{p}": round(ranked[max(0, math.ceil(p / 100 * len(ranked)) - 1)], 4) for p in CUTS} if ranked else {}
    return {**cut, "n": len(ranked)}


def measure(runner: Any, name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """The decision's reference over `cases` (the seed set's test split), kept in the runner's state."""
    model = runner.ada.model(runner.bot.gate_model(name))
    sims = [s for c in cases if (s := nearest(model, c["data"])) is not None]
    reference = spread(sims)
    runner.store.set_state(KEY + name, json.dumps(reference))
    return reference
