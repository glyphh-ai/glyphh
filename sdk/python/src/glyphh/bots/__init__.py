"""Glyphh bots: a bot is a folder (bot.json, agent.md, program.py, skills/) whose program controls its Claude agent.
The runner walks its loop of steps (`run` a program function, `gate` an Ada model that learns from the person's
answers, on one case or with `each` on every item of a list, `ladder` the cheapest of ordered options a gate
predicts will work, `agent` Claude for the steps that need judgment), holding the hard gates bot.json declares
(`limits`, `requires`, approvals, the kill switch); the orchestrator makes bots from a job, decides how far
each is trusted and whether it is kept, and learns from every run. Bots live in ~/.glyphh/bots/<slug>/ (GLYPHH_BOTS
moves them); the `glyphh bot` command drives them.

    from glyphh.bots import Orchestrator, connect

    orch = Orchestrator(connect())
    orch.install("examples/bots/launch_watch")
    result = orch.runner("launch_watch").run()
    if result.status == "needs_input":
        orch.runner("launch_watch").resume(result.options[0])
"""

from .claude import Answer, Claude
from .gates import POLICY, Call, Gate, Policy
from .memory import MEMORY_SPEC, glyphh_models, memory_context, recall, remember
from .orchestrator import GATES, KEEP, OUTCOMES, TRUST, Orchestrator, api_key, connect, slug_of
from .package import KINDS, OUTWARD, TOUCHES, Bot, BotError, bots_root, check_model_name, model_name
from .report import gate_stats, write_report
from .routine import calendar
from .rules import ExprError, holds, parse_answers, parse_expr, validate
from .runner import USER_AGENT, Ctx, End, Runner, RunResult, RunStore, Stop, fill

__all__ = [
    "GATES",
    "KEEP",
    "KINDS",
    "MEMORY_SPEC",
    "OUTCOMES",
    "OUTWARD",
    "POLICY",
    "TOUCHES",
    "TRUST",
    "USER_AGENT",
    "Answer",
    "Bot",
    "BotError",
    "Call",
    "Claude",
    "Ctx",
    "End",
    "ExprError",
    "Gate",
    "Orchestrator",
    "Policy",
    "RunResult",
    "RunStore",
    "Runner",
    "Stop",
    "api_key",
    "bots_root",
    "calendar",
    "check_model_name",
    "connect",
    "fill",
    "gate_stats",
    "holds",
    "parse_answers",
    "parse_expr",
    "validate",
    "write_report",
    "glyphh_models",
    "memory_context",
    "model_name",
    "recall",
    "remember",
    "slug_of",
]
