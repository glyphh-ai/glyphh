"""A project's runs and their turns in the database, as the routes show them; and a run whose pull request waits for
the person, as the approvals queue shows it (beside the bots' runs that wait: GET /v1/bot-approvals), asking "Merge PR
#<n> by <bot>?" (or, with review end, "Merge PR #<n>, the whole run?") with merge or reject."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Project, ProjectRun, ProjectTurn
from glyphh_server.ops.bots import runs as bot_runs
from glyphh_server.ops.bots.views import Question, RunView
from glyphh_server.ops.projects.views import ProjectRunView, TurnView

MISSING: str = "There is no such project run."
OPTIONS: list[str] = ["merge", "reject"]
SUMMED: tuple[str, ...] = ("input_tokens", "output_tokens", "cost_micros")
OF_PROJECT: tuple[Any, ...] = (
    Project.slug.label("project_slug"),
    Project.name.label("project_name"),
    *(Project.repo_url, Project.base_branch, Project.instructions, Project.instructions_path, Project.orchestrator),
    Project.github_installation_id,
)


def _runs() -> Any:
    return select(ProjectRun, *OF_PROJECT).join(Project, Project.id == ProjectRun.project_id)


async def row(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    found = (await conn.execute(_runs().where(ProjectRun.id == run_id))).first()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return found


async def turns(conn: AsyncConnection, run_id: uuid.UUID) -> list[Any]:
    return list(await conn.execute(select(ProjectTurn).where(ProjectTurn.run_id == run_id).order_by(ProjectTurn.n)))


def went(taken: list[Any]) -> list[dict[str, Any]]:
    """The bots' turns as the rules read them (ops/projects/turns.py, idle_row): who, said DONE, changed anything."""
    return [{"bot": t.bot_slug, "done": t.done, "changed": t.status != "unchanged"} for t in taken if t.bot_slug]


def turn_view(t: Any) -> TurnView:
    return TurnView(**{k: getattr(t, k) for k in TurnView.model_fields})


async def view(conn: AsyncConnection, run: Any) -> ProjectRunView:
    shown = [turn_view(t) for t in await turns(conn, run.id)]
    fields = {k: getattr(run, k) for k in ProjectRunView.model_fields.keys() - {"turns", "runs_on", *SUMMED}}
    sums = {k: sum(getattr(t, k) for t in shown) for k in SUMMED}
    return ProjectRunView(**fields, **sums, runs_on=run.rrotor_id, turns=shown)


async def get(conn: AsyncConnection, run_id: uuid.UUID) -> ProjectRunView:
    return await view(conn, await row(conn, run_id))


async def listing(conn: AsyncConnection, project: Any) -> list[ProjectRunView]:
    newest = (
        _runs().where(ProjectRun.project_id == project.id).order_by(ProjectRun.created_at.desc()).limit(bot_runs.SHOWN)
    )
    return [await view(conn, r) for r in await conn.execute(newest)]


def asked(run: Any, turn: Any) -> RunView:
    """A project run's open pull request as the approvals queue shows it: a turn's, or (no turn) the whole run's."""
    if turn is not None:
        data = {k: getattr(turn, k) for k in ("pr_url", "number", "title", "said", "files", "branch", "n")}
        asks, slug, since = f"Merge PR #{turn.number} by {turn.bot_name}?", turn.bot_slug, turn.created_at
    else:
        data = {"pr_url": run.pr_url, "number": run.number, "title": "The whole run", "said": "", "files": []}
        data |= {"branch": run.work_branch, "n": 0}
        asks, slug, since = f"Merge PR #{run.number}, the whole run?", "", run.created_at
    return RunView(
        **{"id": run.id, "bot_slug": slug, "status": run.status, "input": run.task, "output": ""},
        **{"error": "", "log": [], "data": data, "input_tokens": 0, "output_tokens": 0},
        **{"cost_micros": 0, "own_key": True, "runs_on": run.rrotor_id, "kind": "project"},
        **{"project_slug": run.project_slug, "created_at": since, "started_at": run.created_at},
        question=Question(question=asks, options=OPTIONS),
        finished_at=None,
    )


async def waiting(conn: AsyncConnection) -> list[RunView]:
    """The org's project runs whose pull request waits for the person, oldest first."""
    found = _runs().where(ProjectRun.status == "needs_input").order_by(ProjectRun.created_at).limit(bot_runs.SHOWN)
    out = []
    for r in list(await conn.execute(found)):
        turn = await open_turn(conn, r.id)
        if turn is not None or r.pr_url:
            out.append(asked(r, turn))
    return out


async def open_turn(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    return (
        await conn.execute(select(ProjectTurn).where(ProjectTurn.run_id == run_id, ProjectTurn.status == "open"))
    ).first()


async def queue(conn: AsyncConnection) -> list[RunView]:
    """The org's approvals queue: its bots' runs and its projects' pull requests that wait on the person, oldest
    first."""
    both = [*await bot_runs.waiting(conn), *await waiting(conn)]
    return sorted(both, key=lambda r: r.created_at)
