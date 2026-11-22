"""A bot's decisions, readable and trainable (docs/specs/bots.md, 12): one row per item per gate per run, searched,
filtered, sorted and paged; one with its nearest precedents; and the gate trained from them (a decision relabelled or
confirmed right, one or many, a labelled case added, a precedent forgotten), each through the gate's Ada model, as
`wrong` is; how each gate is doing; and a backtest of the gates now. Included by api/bots.py."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request

from glyphh_server.api.auth import Conn
from glyphh_server.api.key_auth import KeyCaller as Caller
from glyphh_server.api.key_auth import KeyPerson as Person
from glyphh_server.ops.bots import cases, decisions, gate_stats, replay, store, teach
from glyphh_server.ops.bots.decision_views import (
    Backtest,
    BacktestIn,
    CaseIn,
    DecisionDetail,
    DecisionPage,
    Forgot,
    IdsIn,
    RelabelIn,
    RelabelManyIn,
    Sort,
    Stats,
    Trained,
    Who,
)

router = APIRouter(tags=["bots"])
Text = Annotated[str | None, Query(max_length=200)]


@router.get("/v1/bots/{slug}/decisions", operation_id="listBotDecisions")
async def list_decisions(
    slug: str,
    caller: Caller,
    conn: Conn,
    q: Annotated[str | None, Query(max_length=200, description="Words its label or fields have (prefixes)")] = None,
    gate: Text = None,
    outcome: Annotated[str | None, Query(max_length=200, description="What the gate said")] = None,
    who: Annotated[Who | None, Query(description="ada, you or default")] = None,
    corrected: Annotated[bool | None, Query(description="Only those corrected (true) or not (false)")] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    sort: Sort = "time",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    run_id: Annotated[uuid.UUID | None, Query(description="Only one run's")] = None,
) -> DecisionPage:
    """Its gates' decisions, one row per item per gate per run, the newest first unless sorted otherwise."""
    find = decisions.Find(q, gate, outcome, who, corrected, since, until, sort, order, cursor, limit, run_id)
    return await decisions.listing(conn, await store.row(conn, slug), find)


@router.get("/v1/bots/{slug}/decisions/stats", operation_id="getBotDecisionStats")
async def decision_stats(
    slug: str, caller: Caller, conn: Conn, gate: Text = None, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> Stats:
    """Per gate, over the last `days`: its decisions by who, its ask rate, agreement and accuracy, day by day."""
    return await gate_stats.stats(conn, await store.row(conn, slug), gate, days)


@router.get("/v1/bot-decisions/{decision_id}", operation_id="getBotDecision")
async def get_decision(decision_id: uuid.UUID, request: Request, who: Person) -> DecisionDetail:
    """One decision, its case, and the nearest precedents its gate stands on for it now."""
    return await replay.detail(request.app.state.bots, who, decision_id)


@router.post("/v1/bot-decisions/{decision_id}/relabel", operation_id="relabelBotDecision")
async def relabel(decision_id: uuid.UUID, body: RelabelIn, request: Request, who: Person) -> Trained:
    """The decision corrected: what it should have been, learned by its gate as a precedent."""
    return await teach.relabel(request.app.state.bots, who, [decision_id], body.outcome)


@router.post("/v1/bot-decisions/{decision_id}/confirm", operation_id="confirmBotDecision")
async def confirm(decision_id: uuid.UUID, request: Request, who: Person) -> Trained:
    """The decision said right: kept as a precedent of its gate (unless it is one already)."""
    return await teach.confirm(request.app.state.bots, who, [decision_id])


@router.post("/v1/bots/{slug}/decisions/relabel", operation_id="relabelBotDecisions")
async def relabel_many(slug: str, body: RelabelManyIn, request: Request, who: Person) -> Trained:
    """Up to 200 of one gate's decisions relabelled with one outcome, each learned as a precedent."""
    return await teach.relabel(request.app.state.bots, who, body.ids, body.outcome, slug)


@router.post("/v1/bots/{slug}/decisions/confirm", operation_id="confirmBotDecisions")
async def confirm_many(slug: str, body: IdsIn, request: Request, who: Person) -> Trained:
    """Up to 200 of one gate's decisions said right, each kept as a precedent."""
    return await teach.confirm(request.app.state.bots, who, body.ids, slug)


@router.post("/v1/bots/{slug}/cases", operation_id="addBotCase", status_code=201)
async def add_case(slug: str, body: CaseIn, request: Request, who: Person) -> Trained:
    """A labelled case added to a gate by hand: its item's fields (the case made as a run makes it) or the case."""
    return await cases.add(request.app.state.bots, who, slug, body)


@router.delete("/v1/bots/{slug}/gates/{gate}/precedents/{precedent_id}", operation_id="forgetBotPrecedent")
async def forget(slug: str, gate: str, precedent_id: str, request: Request, who: Person) -> Forgot:
    """One precedent forgotten by the gate's model (what was learned from it stays until its next learn)."""
    return await cases.forget(request.app.state.bots, who, slug, gate, precedent_id)


@router.post("/v1/bots/{slug}/backtest", operation_id="backtestBotGates")
async def backtest(slug: str, body: BacktestIn, request: Request, who: Person) -> Backtest:
    """The newest decisions replayed against their gates now, under each gate's policy: what would change, how many
    it would ask about, how many it now gets right. Nothing is recorded."""
    return await teach.backtest(request.app.state.bots, who, slug, body)
