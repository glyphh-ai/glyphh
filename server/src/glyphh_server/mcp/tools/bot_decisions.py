"""A Glyphh bot's decisions, read and trained through the connector (docs/specs/bots.md, 12), enough for Claude to
train a bot end to end: find its decisions (search, filter, sort, page), read one with the precedents behind it,
relabel what a gate got wrong (one or many), confirm what it got right, add a labelled case, forget a precedent, see
how each gate is doing, and backtest the gates now. The tools that reach Ada make their own transactions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, dump
from glyphh_server.mcp.tools.bots import SLUG
from glyphh_server.ops.bots import cases, decisions, gate_stats, replay, store, teach
from glyphh_server.ops.bots.decision_views import (
    BacktestIn,
    CaseIn,
    DecisionView,
    IdsIn,
    RelabelManyIn,
    Sort,
    Trained,
    Who,
)


class Find(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    q: str | None = Field(None, max_length=200, description="Words its label or fields have (each a prefix)")
    gate: str | None = Field(None, max_length=100)
    outcome: str | None = Field(None, max_length=200, description="What the gate said")
    who: Who | None = Field(None, description="ada (its gate decided), you (the person was asked) or default")
    corrected: bool | None = Field(None, description="true: only those corrected; false: only those not")
    since: datetime | None = None
    until: datetime | None = None
    sort: Sort = "time"
    order: str = Field("desc", pattern="^(asc|desc)$")
    cursor: str | None = Field(None, max_length=500, description="The next_cursor of the page before")
    limit: int = Field(25, ge=1, le=100)
    run_id: uuid.UUID | None = Field(None, description="Only one run's decisions (bot_runs lists them)")


class DecisionId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: uuid.UUID


class Relabel(DecisionId):
    outcome: str = Field(min_length=1, max_length=200, description="What it should have been: one of its outcomes")


class Many(RelabelManyIn):
    slug: str = SLUG


class Confirm(IdsIn):
    slug: str = SLUG


class AddCase(CaseIn):
    slug: str = SLUG


class Forget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    gate: str = Field(min_length=1, max_length=100)
    precedent_id: str = Field(min_length=1, max_length=200, description="A precedent's id (bot_decision names them)")


class StatsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    gate: str | None = Field(None, max_length=100)
    days: int = Field(30, ge=1, le=365, description="How many days back")


class Backtest(BacktestIn):
    slug: str = SLUG


def pct(p: float | None) -> str:
    return "no P" if p is None else f"{round(p * 100)}%"


def line(d: DecisionView) -> str:
    who = {"ada": f"Ada {pct(d.confidence)}", "you": "you", "default": "its default"}[d.who]
    fixed = f", corrected to {d.corrected}" if d.corrected and d.corrected != d.outcome else ""
    right = ", confirmed right" if d.confirmed else ""
    return f"[{d.outcome}] {d.label} (gate {d.gate}, by {who}{fixed}{right}; {d.at:%Y-%m-%d %H:%M}; id {d.id})"


def trained(done: Trained) -> Done:
    return Done("\n".join([f"{done.said}.", *(line(d) for d in done.decisions)]), dump(done))


async def find(ctx: Context, args: Find) -> Done:
    asked = decisions.Find(**args.model_dump(exclude={"slug"}))
    page = await decisions.listing(ctx.conn, await store.row(ctx.conn, args.slug), asked)
    head = f"{page.total} decision{'s' * (page.total != 1)}" + (
        f"; next page: cursor {page.next_cursor}" if page.next_cursor else ""
    )
    return Done("\n".join([head, *(line(d) for d in page.decisions)]), dump(page))


async def one(ctx: Context, args: DecisionId) -> Done:
    d = await replay.detail(ctx.bots, ctx.who, args.decision_id)
    fields = [f"  {k}: {v[:300]}" for k, v in d.fields.items()]
    near = [
        f"  {p.id}: {p.outcome}, {pct(p.similarity)} alike" + (f" ({p.label})" if p.label else "") for p in d.precedents
    ]
    said = [
        line(d),
        f"Outcomes: {', '.join(d.outcomes)}",
        "Fields:",
        *fields,
        "Nearest precedents:",
        *(near or ["  none"]),
    ]
    return Done("\n".join(said), dump(d))


async def relabel(ctx: Context, args: Relabel) -> Done:
    return trained(await teach.relabel(ctx.bots, ctx.who, [args.decision_id], args.outcome))


async def relabel_many(ctx: Context, args: Many) -> Done:
    return trained(await teach.relabel(ctx.bots, ctx.who, args.ids, args.outcome, args.slug))


async def confirm(ctx: Context, args: Confirm) -> Done:
    return trained(await teach.confirm(ctx.bots, ctx.who, args.ids, args.slug))


async def add_case(ctx: Context, args: AddCase) -> Done:
    return trained(await cases.add(ctx.bots, ctx.who, args.slug, CaseIn(**args.model_dump(exclude={"slug"}))))


async def forget(ctx: Context, args: Forget) -> Done:
    gone = await cases.forget(ctx.bots, ctx.who, args.slug, args.gate, args.precedent_id)
    return Done(f"Gate {gone.gate} forgot {gone.id}; it holds {gone.precedents} precedents.", dump(gone))


async def stats(ctx: Context, args: StatsArgs) -> Done:
    found = await gate_stats.stats(ctx.conn, await store.row(ctx.conn, args.slug), args.gate, args.days)
    lines = [
        f"{g.gate}: {g.decisions} decisions (Ada {g.by['ada']}, you {g.by['you']}, default {g.by['default']}); "
        f"asks {pct(g.ask_rate)}, agreement {pct(g.agreement)}, accuracy {pct(g.accuracy)}; "
        f"{g.corrected} corrected, {g.confirmed} confirmed"
        for g in found.gates
    ]
    return Done("\n".join(lines) or "The bot has no gates.", dump(found))


async def backtest(ctx: Context, args: Backtest) -> Done:
    done = await teach.backtest(ctx.bots, ctx.who, args.slug, BacktestIn(**args.model_dump(exclude={"slug"})))
    head = (f"Replayed {done.replayed}: {done.same} the same, {len(done.changed)} would change or ask; it would ask "
            f"about {done.would_ask} and now gets {done.right_now} right.")  # fmt: skip
    rows = [
        f"{c.decision.label} (gate {c.decision.gate}): {c.then} -> {c.now}{' (asks)' if c.ask else ''}"
        for c in done.changed
    ]
    return Done("\n".join([head, *rows]), dump(done))
