"""A bot's decisions read and its gates trained, for the routes and the connector's tools alike (docs/specs/bots.md,
11): each on transactions of its own, the person's org entered, so a tool runs it as a route does."""

import uuid
from typing import Any

from glyphh_server.db import tenancy
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import decisions, replay, store, training
from glyphh_server.ops.bots.decision_views import Backtest, BacktestIn, Trained
from glyphh_server.ops.bots.goes import Goes


async def bot(svc: Goes, who: Principal, slug: str) -> Any:
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await store.row(conn, slug)


async def _of(svc: Goes, who: Principal, ids: list[uuid.UUID], slug: str | None) -> tuple[Any, list[Any]]:
    """The decisions (of the bot `slug`, when given; else of the first one's bot) and their bot."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        if slug is None:
            _, found = await decisions.row(conn, ids[0])
        else:
            found = await store.row(conn, slug)
        return found, await decisions.rows(conn, found, ids)


async def relabel(svc: Goes, who: Principal, ids: list[uuid.UUID], outcome: str, slug: str | None = None) -> Trained:
    found, rows = await _of(svc, who, ids, slug)
    return await training.relabel(svc, who, found, rows, outcome)


async def confirm(svc: Goes, who: Principal, ids: list[uuid.UUID], slug: str | None = None) -> Trained:
    found, rows = await _of(svc, who, ids, slug)
    return await training.confirm(svc, who, found, rows)


async def backtest(svc: Goes, who: Principal, slug: str, body: BacktestIn) -> Backtest:
    return await replay.backtest(svc, who, await bot(svc, who, slug), body)
