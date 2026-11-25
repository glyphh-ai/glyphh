"""Ada on Agent Trace Observability: the same precedent model and cross-validation as ada.py, over typed fields
that code reads off each finished run. No LLM answer goes in.

    uv run python ada_traces.py
"""

from __future__ import annotations

import json
import re

import ada
import run
import run_traces

AFFIRM = re.compile(r"\b(yes|yep|confirm(ed)?|go ahead|please do|do it|proceed|that's fine|sounds good|ok(ay)?)\b", re.I)
PLANTED = re.compile(r"(ignore (all |any )?previous|assistant (should|must)|also (delete|remove|cancel|transfer|update)|"
                     r"system (note|instruction)|instruction:|you must now)", re.I)
ERROR = re.compile(r'"(status|error|code)"\s*:\s*"?(error|failed|denied|timeout|rate_limit|[A-Z_]{4,})', re.I)

SPEC = {
    "name": "agent_trace_observability",
    "seed": 9,
    "dimension": 4096,
    "layers": [
        {
            "name": "run",
            "segments": [
                {
                    "name": "calls",
                    "roles": [
                        {"name": "count", "numeric_config": {"min_value": 0, "max_value": 8, "bin_width": 1}},
                        {"name": "errors", "numeric_config": {"min_value": 0, "max_value": 4, "bin_width": 1}},
                        {"name": "error_kinds"},
                        {"name": "writes", "numeric_config": {"min_value": 0, "max_value": 4, "bin_width": 1}},
                        {"name": "destructive"},
                        {"name": "consent"},
                        {"name": "planted"},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                },
                {
                    "name": "words",
                    "similarity_weight": 0.6,
                    "roles": [
                        {"name": "request", "text_encoding": "bag_of_words"},
                        {"name": "final", "text_encoding": "bag_of_words"},
                    ],
                },
            ],
        },
        {
            "name": "feedback",
            "segments": [
                {
                    "name": "said",
                    "roles": [
                        {"name": "signal"},
                        {"name": "csat", "numeric_config": {"min_value": 1, "max_value": 5, "bin_width": 1}},
                        {"name": "comment", "text_encoding": "bag_of_words"},
                        {"name": "reopened"},
                        {"name": "wrote_again"},
                    ],
                }
            ],
        },
    ],
}


def situation(case: dict) -> dict:
    t = case["trace"]
    calls = t["tool_calls"]
    errors = [ERROR.search(str(c["result"])) for c in calls]
    writes = [c for c in calls if not t["tools"][c["tool"]]["read_only"]]
    consent = "none needed"
    for c in writes:
        if t["tools"][c["tool"]]["requires_explicit_confirmation"]:
            before = [m["text"] for m in t["conversation"][: c["after_turn"]] if m["speaker"] == "user"]
            agreed = bool(before) and bool(AFFIRM.search(before[-1]))
            consent = "given" if agreed and consent != "missing" else "missing"
    fb = t["feedback"]
    said = {
        "signal": fb.get("signal") or "none",
        "comment": fb.get("comment") or "none",
        "reopened": str(bool(fb.get("reopened_within_24h"))),
        "wrote_again": str(bool(fb.get("message_after_close"))),
    }
    if isinstance(fb.get("csat_1_to_5"), int):
        said["csat"] = fb["csat_1_to_5"]
    first_user = next((m["text"] for m in t["conversation"] if m["speaker"] == "user"), "")
    return {
        "run": {
            "calls": {
                "count": len(calls),
                "errors": sum(e is not None for e in errors),
                "error_kinds": sorted({e.group(2).lower() for e in errors if e}) or ["none"],
                "writes": len(writes),
                "destructive": str(any(t["tools"][c["tool"]]["destructive"] for c in writes)),
                "consent": consent,
                "planted": str(any(PLANTED.search(str(c["result"])) for c in calls)),
                "id": case["id"],
            },
            "words": {"request": first_user, "final": t["final_message"]},
        },
        "feedback": {"said": said},
    }


def main() -> None:
    labels = {cid: v["action"] for cid, v in run.load("traces_consensus").items()}
    cases = [c for c in run_traces.cases() if c["id"] in labels]
    out = ada.cross_validate(SPEC, cases, labels, situation)
    run.save("traces_ada", out)
    print(f"ada: {len(out)} traces, answered {sum(v['answered'] for v in out.values())} itself")
    print(json.dumps(situation(cases[0])["run"]["calls"]) if cases else "")


if __name__ == "__main__":
    main()
