"""The orchestrator's hold on the crew (docs/specs/bot-agent-loop.md, 8): start a run of the crew on its latest
workspace (the project the Bots screen made for a repo and branch, ops/projects/crew.py), read how its latest run
stands, and stop it. A crew's pull requests still wait for the person where they always did."""

import uuid
from typing import Any

from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import Project, ProjectRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots.agent.tools import Tool

NO_CREW: str = "The crew has no workspace yet: the person chooses a repository for it on the Bots screen first."
NO_RUN: str = "The crew has not run yet."
TASK: dict[str, Any] = {
    "type": "object",
    "properties": {"task": {"type": "string", "description": "What the crew should do"}},
    "required": ["task"],
}
NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}}


async def _latest(svc: Any, org_id: uuid.UUID) -> tuple[Any, Any]:
    """The crew's latest workspace, and its latest run there (either may be None)."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        project = (await conn.execute(select(Project).order_by(Project.updated_at.desc()).limit(1))).first()
        if project is None:
            return None, None
        newest = select(ProjectRun).where(ProjectRun.project_id == project.id)
        run = (await conn.execute(newest.order_by(ProjectRun.created_at.desc()).limit(1))).first()
    return project, run


def _stands(project: Any, run: Any) -> dict[str, Any]:
    return {"workspace": project.name, "status": run.status, "task": run.task, "why": run.error or run.ended or ""}


def crew_tools(svc: Any, bot: Any, user_id: uuid.UUID | None) -> list[Tool]:
    who = Principal(user_id=user_id or bot.id, org_id=bot.org_id, role="member")

    async def crew_start(given: dict[str, Any]) -> Any:
        project, _ = await _latest(svc, bot.org_id)
        if project is None:
            raise ValueError(NO_CREW)
        try:
            made = await svc.projects.start(who, project.slug, str(given.get("task") or ""))
        except GlyphhError as err:
            raise ValueError(f"The crew could not start: {err.message}") from err
        return {"workspace": project.name, "status": made.status, "task": made.task}

    async def crew_status(given: dict[str, Any]) -> Any:
        project, run = await _latest(svc, bot.org_id)
        if project is None or run is None:
            raise ValueError(NO_CREW if project is None else NO_RUN)
        return _stands(project, run)

    async def crew_stop(given: dict[str, Any]) -> Any:
        project, run = await _latest(svc, bot.org_id)
        if project is None or run is None:
            raise ValueError(NO_CREW if project is None else NO_RUN)
        try:
            await svc.projects.cancel(who, run.id)
        except GlyphhError as err:
            raise ValueError(err.message) from err
        return {"workspace": project.name, "status": "stopped"}

    return [
        Tool("crew_start", "crew_start", "Started the crew", "Give the crew a task on its latest workspace.", TASK,
             True, call=crew_start),
        Tool("crew_status", "crew_status", "Checked on the crew", "How the crew's latest run stands.", NO_ARGS, True,
             call=crew_status),
        Tool("crew_stop", "crew_stop", "Stopped the crew", "Stop the crew's run that is going.", NO_ARGS, True,
             call=crew_stop),
    ]  # fmt: skip
