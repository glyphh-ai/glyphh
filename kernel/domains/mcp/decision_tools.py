"""
MCP decision tools — sim across decisions through the same surface.

record_decision stores a decided case as precedent (one-shot, no
training run, persisted in the runtime's decision store); decide
measures similarity across every recorded decision and answers with an
outcome distribution, a confidence with defined semantics, and the full
fact tree citing each precedent. Shares the default DecisionSpace with
the /v1/decide HTTP routes, so precedent recorded on either surface
serves both.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp.types import Tool

logger = logging.getLogger(__name__)

_EVENT_SCHEMA = {
    "type": "array",
    "description": ("Optional ordered events (each a flat object) — "
                    "use when the order of what happened matters"),
    "items": {"type": "object"},
}


def decision_tool_definitions() -> List[Tool]:
    return [
        Tool(
            name="decide",
            description=(
                "Measure similarity across all recorded decisions and "
                "return the outcome distribution, a confidence (consensus "
                "among sufficient precedent), and a fact tree citing every "
                "matched precedent. Declines to answer when precedent is "
                "too thin, naming the nearest case."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "situation": {
                        "type": "object",
                        "description": "Flat attributes of the decision at hand",
                    },
                    "events": _EVENT_SCHEMA,
                    "k": {"type": "integer",
                          "description": "Precedents to consider (default 10)"},
                },
                "required": ["situation"],
            },
        ),
        Tool(
            name="record_decision",
            description=(
                "Store a decided case as precedent for future decide calls. "
                "One-shot and persistent — no training run."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "situation": {"type": "object"},
                    "outcome": {"type": "string"},
                    "facts": {"type": "object",
                              "description": "Free-form supporting facts, "
                                             "cited back in future answers"},
                    "events": _EVENT_SCHEMA,
                },
                "required": ["situation", "outcome"],
            },
        ),
    ]


DECISION_TOOL_NAMES = {"decide", "record_decision"}


async def handle_decision_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    from glyphh.decision.store import get_default_space

    space = get_default_space()

    if name == "decide":
        situation = args.get("situation") or {}
        if not situation:
            raise ValueError("Missing 'situation'")
        answer = space.query(
            situation,
            events=args.get("events"),
            k=int(args["k"]) if args.get("k") else None,
        )
        return answer.to_json()

    if name == "record_decision":
        situation = args.get("situation") or {}
        outcome = (args.get("outcome") or "").strip()
        if not situation or not outcome:
            raise ValueError("Missing 'situation' or 'outcome'")
        decision_id = space.record(
            situation, outcome,
            facts=args.get("facts"),
            events=args.get("events"),
        )
        return {"decision_id": decision_id, "precedents": len(space)}

    raise ValueError(f"Unknown decision tool: {name}")
