"""A swarm's runs and their turns in the database, as the routes show them; and a run whose pull request waits for the
person, as the approvals queue shows it (beside the bots' runs that wait: GET /v1/bot-approvals), asking "Merge PR
#<n> by <bot>?" with merge or reject."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Swarm, SwarmRun, SwarmTurn
from glyphh_server.ops.bots import runs as bot_runs
from glyphh_server.ops.bots.views import Question, RunView
from glyphh_server.ops.swarms.views import SwarmRunView, TurnView

MISSING: str = "There is no such swarm run."
OPTIONS: list[str] = ["merge", "reject"]


async def row(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    found = (
        await conn.execute(
            select(SwarmRun, Swarm.slug.label("swarm_slug"), Swarm.repo_url, Swarm.base_branch)
            .join(Swarm, Swarm.id == SwarmRun.swarm_id)
            .where(SwarmRun.id == run_id)
        )
    ).first()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return found


async def turns(conn: AsyncConnection, run_id: uuid.UUID) -> list[Any]:
    return list(await conn.execute(select(SwarmTurn).where(SwarmTurn.run_id == run_id).order_by(SwarmTurn.n)))


def turn_view(t: Any) -> TurnView:
    return TurnView(**{k: getattr(t, k) for k in TurnView.model_fields})


async def view(conn: AsyncConnection, run: Any) -> SwarmRunView:
    shown = [turn_view(t) for t in await turns(conn, run.id)]
    fields = {k: getattr(run, k) for k in SwarmRunView.model_fields.keys() - {"turns", "runs_on"}}
    return SwarmRunView(**fields, runs_on=run.rrotor_id, turns=shown)


async def get(conn: AsyncConnection, run_id: uuid.UUID) -> SwarmRunView:
    return await view(conn, await row(conn, run_id))


async def listing(conn: AsyncConnection, swarm: Any) -> list[SwarmRunView]:
    newest = (
        select(SwarmRun, Swarm.slug.label("swarm_slug"))
        .join(Swarm, Swarm.id == SwarmRun.swarm_id)
        .where(SwarmRun.swarm_id == swarm.id)
        .order_by(SwarmRun.created_at.desc())
        .limit(bot_runs.SHOWN)
    )
    return [await view(conn, r) for r in await conn.execute(newest)]


def asked(run: Any, turn: Any) -> RunView:
    """A swarm run's open pull request as the approvals queue shows it."""
    data = {k: getattr(turn, k) for k in ("pr_url", "number", "title", "said", "files", "branch", "n", "round")}
    question = Question(question=f"Merge PR #{turn.number} by {turn.bot_name}?", options=OPTIONS)
    return RunView(
        **{"id": run.id, "bot_slug": turn.bot_slug, "status": run.status, "input": run.task, "output": ""},
        **{"error": "", "log": [], "data": data, "question": question, "input_tokens": 0, "output_tokens": 0},
        **{"cost_micros": 0, "own_key": True, "runs_on": run.rrotor_id, "kind": "swarm"},
        **{"swarm_slug": run.swarm_slug, "created_at": turn.created_at, "started_at": run.created_at},
        finished_at=None,
    )


async def waiting(conn: AsyncConnection) -> list[RunView]:
    """The org's swarm runs whose pull request waits for the person, oldest first."""
    found = (
        select(SwarmRun, Swarm.slug.label("swarm_slug"))
        .join(Swarm, Swarm.id == SwarmRun.swarm_id)
        .where(SwarmRun.status == "needs_input")
        .order_by(SwarmRun.created_at)
        .limit(bot_runs.SHOWN)
    )
    out = []
    for r in list(await conn.execute(found)):
        if (turn := await open_turn(conn, r.id)) is not None:
            out.append(asked(r, turn))
    return out


async def open_turn(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    return (await conn.execute(select(SwarmTurn).where(SwarmTurn.run_id == run_id, SwarmTurn.status == "open"))).first()


async def queue(conn: AsyncConnection) -> list[RunView]:
    """The org's approvals queue: its bots' runs and its swarms' pull requests that wait on the person, oldest
    first."""
    both = [*await bot_runs.waiting(conn), *await waiting(conn)]
    return sorted(both, key=lambda r: r.created_at)
