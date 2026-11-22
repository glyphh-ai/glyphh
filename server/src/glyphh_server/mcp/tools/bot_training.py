"""The connector's tools for a bot's decisions and training (handlers in bot_decisions.py): what each does, as Claude
reads it, whether it only reads and whether a write replaces or removes what a gate had learned."""

from glyphh_server.mcp.tools import bot_decisions as h
from glyphh_server.mcp.tools.base import Tool

ITEMS = "one row per item per gate per run, each with its readable label, who decided (ada, you or default)"
TOOLS: tuple[Tool, ...] = (
    Tool(
        "bot_decisions",
        "A bot's decisions",
        f"Find a bot's gate decisions: {ITEMS}, its confidence and whether it was corrected. Search words (prefixes "
        "of its label and fields), filter by gate, outcome, who, corrected and a time range, sort by time, "
        "confidence, gate or outcome, and page with next_cursor. Start here to train a bot: find what its gates got "
        "wrong or were unsure of, then bot_relabel or bot_confirm them.",
        h.Find,
        h.find,
        True,
    ),
    Tool(
        "bot_decision",
        "A bot decision",
        "One decision: the item's fields, the gate's outcomes, its case, and the nearest precedents the gate stands "
        "on for it now (each id is what bot_forget_case takes).",
        h.DecisionId,
        h.one,
        True,
    ),
    Tool(
        "bot_relabel",
        "Relabel a bot decision",
        "Correct one decision: the outcome it should have had, learned by its gate's Ada model as a precedent "
        "(replacing what the gate had learned for that case).",
        h.Relabel,
        h.relabel,
        destructive=True,
    ),
    Tool(
        "bot_relabel_many",
        "Relabel bot decisions",
        "Correct up to 200 decisions of one gate with one outcome (ids from bot_decisions), each learned as a "
        "precedent, replacing what the gate had learned for those cases.",
        h.Many,
        h.relabel_many,
        destructive=True,
    ),
    Tool(
        "bot_confirm",
        "Confirm bot decisions",
        "Say up to 200 decisions of one gate were right: each kept as a precedent of its gate (one the person "
        "answered is one already), so the gate asks less about cases like it.",
        h.Confirm,
        h.confirm,
        destructive=False,
    ),
    Tool(
        "bot_add_case",
        "Add a case to a bot's gate",
        "Teach a gate a labelled case by hand: the item's fields as a run gives them (the gate's case is made from "
        "them as a run makes it), or the case itself in the gate's spec's shape, with its outcome.",
        h.AddCase,
        h.add_case,
        destructive=False,
    ),
    Tool(
        "bot_forget_case",
        "Forget a bot gate's precedent",
        "Forget one precedent of a gate (its id from bot_decision's nearest precedents); a case added by hand is "
        "removed. What was learned from it stays until the gate's next learn.",
        h.Forget,
        h.forget,
        destructive=True,
    ),
    Tool(
        "bot_gate_stats",
        "How a bot's gates are doing",
        "Per gate over the last days: decisions by Ada, you and the default; its ask rate; its agreement (Ada's "
        "guess matched the person's answer); its accuracy (Ada's own calls the person checked that were right); "
        "corrections and confirmations; and each of those day by day.",
        h.StatsArgs,
        h.stats,
        True,
    ),
    Tool(
        "bot_backtest",
        "Backtest a bot's gates",
        "Replay a bot's newest decisions (up to 200, one gate or all) against its gates as they are now, under each "
        "gate's policy: which would change, how many it would ask about, how many it now gets right. Run it after "
        "training to see what changed. Nothing is recorded.",
        h.Backtest,
        h.backtest,
        True,
    ),
)
DETACHED: frozenset[str] = frozenset(
    {
        "bot_decision",
        "bot_relabel",
        "bot_relabel_many",
        "bot_confirm",
        "bot_add_case",
        "bot_forget_case",
        "bot_backtest",
    }
)
