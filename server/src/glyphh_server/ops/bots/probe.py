"""A gate probed for what it holds no class of (docs/specs/bots.md, 9): the Resume Screener's `made` gate holds only
generated applications (some, mostly, fully), so an application written by a person is one with no close generated
precedent. When the gate is seeded, its nearest precedent's similarity (the gate's own, on Ada's receipts) is measured
over the seed set's test applicants, never recorded, and kept in the runner's state as the reference (p5 to p95);
the `probe_generated` step then asks the gate about each application and sends on to it only those whose nearest
precedent is at least as close as the reference's p5, the rest answered human, with how near they came."""

import json
import math
from typing import Any

from glyphh.bots.runner import fill

KEY: str = "_glyphh_probe:"
CUTS: tuple[int, ...] = (5, 25, 50, 75, 95)
FLOOR: str = "p5"


def nearest(model: Any, case: dict[str, Any]) -> float | None:
    """The similarity of the gate's nearest precedent to the case (None: it holds none)."""
    receipts = getattr(model.decide(case), "receipts", None) or []
    sims = [float(r["sim"]) for r in receipts if isinstance(r, dict) and isinstance(r.get("sim"), int | float)]
    return max(sims) if sims else None


def spread(sims: list[float]) -> dict[str, Any]:
    """The p5 to p95 of the similarities (nearest rank), and how many they were."""
    ranked = sorted(sims)
    cut = {f"p{p}": round(ranked[max(0, math.ceil(p / 100 * len(ranked)) - 1)], 4) for p in CUTS} if ranked else {}
    return {**cut, "n": len(ranked)}


def measure(runner: Any, name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """The gate's reference over `cases` (the seed set's test split), kept in the runner's state."""
    model = runner.ada.model(runner.bot.gate_model(name))
    sims = [s for c in cases if (s := nearest(model, c["data"])) is not None]
    reference = spread(sims)
    runner.store.set_state(KEY + name, json.dumps(reference))
    return reference


def unprobed(given: dict[str, Any], reference: dict[str, Any] | None = None) -> dict[str, Any]:
    apps = [a for a in given.get("applications") or [] if isinstance(a, dict)]
    return {"generated": apps, "human": [], "reference": reference}


def probed(ctx: Any, given: Any) -> dict[str, Any]:
    """`{applications, gate}` → {generated (sent on to the gate), human [{id, nearest}], reference}; a gate with no
    reference yet (not seeded) is sent them all."""
    given = given if isinstance(given, dict) else {}
    name = str(given.get("gate") or "")
    kept = ctx.state(KEY + name) if name in ctx.bot.gates else None
    reference = json.loads(kept) if kept else None
    if not reference or FLOOR not in reference:
        return unprobed(given, reference)
    model = ctx.ada.model(ctx.bot.gate_model(name))
    out = unprobed(given, reference) | {"generated": []}
    for app in unprobed(given)["generated"]:
        near = nearest(model, fill(ctx.bot.gates[name]["case"], {"item": app}))
        if near is not None and near >= reference[FLOOR]:
            out["generated"].append(app)
        else:
            out["human"].append({"id": app.get("id"), "nearest": None if near is None else round(near, 4)})
    return out
