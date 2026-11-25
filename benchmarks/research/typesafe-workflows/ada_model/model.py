"""security_incidents: the benchmark's one Ada model on rrotor. A case is recorded once with the consensus's answer
to every workflow question it was asked (its named outputs); refresh() learns and calibrates each question;
decide_all() answers the questions a workflow step asks, one decision per question. The spec beside this file
(spec.json, written by ada_runtime.py from ada.py) says what a case looks like; the Ada part brings the kernel."""

from __future__ import annotations

from typing import Any

from rrotor import Result, ada


def load(ctx: Any) -> None:
    ada.open(ctx)


def start(ctx: Any, inputs: dict[str, Any]) -> Result:
    return Result.done({"precedents": len(ctx.ada), "outputs": ctx.ada.outputs()})


def record(ctx: Any, inputs: dict[str, Any]) -> Result:
    rid = ctx.ada.record(inputs["data"], outcomes=inputs.get("outcomes"))
    return Result.done({"id": rid, "precedents": len(ctx.ada)})


def refresh(ctx: Any, inputs: dict[str, Any]) -> Result:
    out = ctx.ada.refresh(clearance=ctx.clearance)
    return Result.done({"tau": {name: o["tau"] for name, o in out.items()}, "precedents": len(ctx.ada)})


def decide_all(ctx: Any, inputs: dict[str, Any]) -> Result:
    return Result.done(ctx.ada.decide_all(inputs["data"], clearance=ctx.clearance, outputs=inputs.get("outputs")))
