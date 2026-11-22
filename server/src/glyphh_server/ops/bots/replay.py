"""What reads a bot's gates as they are now, on the bot's own Ada key, never its runner's state (so it may run while a
run of the bot is going) (docs/specs/bots.md, 12): a decision with its nearest precedents, and a backtest that replays
recent decisions against each gate now, under its policy, saying which would change."""

import asyncio
import uuid
from typing import Any

from glyphh.bots import model_name
from glyphh.bots.gates import Policy
from glyphh.bots.runner import held
from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid
from glyphh_server.models import BotDecision
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import unseal
from glyphh_server.ops.bots import decisions, package
from glyphh_server.ops.bots.decision_views import Backtest, BacktestIn, Change, DecisionDetail, Precedent
from glyphh_server.ops.bots.goes import Goes

D = BotDecision
NEAREST: int = 8


def gate_model(bot: Any, gate: str) -> str:
    return str(model_name("bot", package.loop_slug(bot.slug), "gate", gate))


async def on_ada(svc: Goes, bot: Any, act: Any) -> Any:
    """`act` on the bot's Ada (by its own key) in a worker thread."""
    ada = svc.ada_for(unseal(svc.settings.secret_key, bot.ada_key))
    return await asyncio.to_thread(act, ada)


def nearest(ada: Any, bot: Any, case: Any, gate: str) -> list[dict[str, Any]]:
    name = gate_model(bot, gate)
    if not held(ada, name):
        return []
    receipts = getattr(ada.model(name).decide(case), "receipts", None) or []
    return [r for r in receipts if isinstance(r, dict) and r.get("id") is not None][:NEAREST]


async def detail(svc: Goes, who: Principal, decision_id: uuid.UUID) -> DecisionDetail:
    """The decision, its case, and the precedents its gate stands on for that case now (each named by its decision
    when it is one of the bot's)."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        d, bot = await decisions.row(conn, decision_id)
    live = d.gate in decisions.outcomes(bot)  # a gate since taken off the bot has no model to ask
    receipts = await on_ada(svc, bot, lambda ada: nearest(ada, bot, d.case, d.gate)) if live else []
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        known = await decisions.by_precedent(conn, bot, [str(r["id"]) for r in receipts])
    shown = []
    for r in receipts:
        mine = known.get(str(r["id"]))
        sim = r.get("sim")
        shown.append(Precedent(
            id=str(r["id"]), outcome=r.get("outcome"), similarity=float(sim) if isinstance(sim, int | float) else None,
            label=mine.label if mine else None, decision_id=mine.id if mine else None,
        ))  # fmt: skip
    base = decisions.view(d, decisions.outcomes(bot))
    return DecisionDetail(**base.model_dump(), case=d.case, precedents=shown)


def judged(ada: Any, bot: Any, d: Any, counts: dict[str, int]) -> Any:
    """The gate's call on the decision's case now, under its policy."""
    name = gate_model(bot, d.gate)
    if name not in counts:
        counts[name] = held(ada, name)
    n = counts[name]
    decided = ada.model(name).decide(d.case) if n else None
    return Policy.of(d.gate, bot.spec["gates"][d.gate]).judge(decided, n, str(d.id))


async def recent(svc: Goes, who: Principal, bot: Any, body: BacktestIn) -> list[Any]:
    gates = list(decisions.outcomes(bot))
    found = select(D, decisions._run_id()).where(D.bot_id == bot.id, D.gate.in_([body.gate] if body.gate else gates))
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return list(await conn.execute(found.order_by(D.at.desc(), D.id.desc()).limit(body.limit)))


async def backtest(svc: Goes, who: Principal, bot: Any, body: BacktestIn) -> Backtest:
    """The newest decisions replayed against their gates now: which would change, and how many it would ask about
    or now get right (what each is: its correction, else what was said). Nothing is recorded."""
    if body.gate is not None and body.gate not in decisions.outcomes(bot):
        raise Invalid(f"{bot.slug} has no gate {body.gate}.", reason="gate")
    rows = await recent(svc, who, bot, body)

    def act(ada: Any) -> list[Any]:
        counts: dict[str, int] = {}
        return [judged(ada, bot, d, counts) for d in rows]

    calls = await on_ada(svc, bot, act) if rows else []
    gates = decisions.outcomes(bot)
    changed, asks, right = [], 0, 0
    for d, call in zip(rows, calls, strict=True):
        then = d.corrected or d.outcome
        asks += int(call.ask)
        right += int(call.outcome == then and not call.ask)
        if call.outcome != then or call.ask:
            view = decisions.view(d, gates)
            changed.append(Change(decision=view, then=then, now=call.outcome, ask=call.ask, confidence=call.p))
    same = len(rows) - len(changed)
    return Backtest(replayed=len(rows), same=same, changed=changed, would_ask=asks, right_now=right)
