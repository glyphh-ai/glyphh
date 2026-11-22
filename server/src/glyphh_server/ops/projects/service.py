"""The org's projects' runs (app.state.bots.projects): started (a task given, or the instructions alone; refused
while Glyphh's GitHub App is not installed on its repo, with no bot left in the crew, while its rrotor is not linked,
or on Glyphh cloud with no Anthropic key to run on), a pull request that waits answered (a turn's, or with review end
the whole run's), and a run cancelled (its step out stopped; an open pull request stays open on GitHub). The steps'
results move a run on (ops/projects/results.py). At the server's start, this machine's runs on Glyphh cloud that a
step was out for are failed: their tasks went with the process."""

import asyncio
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, GlyphhError, Invalid, Unavailable
from glyphh_server.models import Project, ProjectRun, ProjectTurn
from glyphh_server.models.project import TURN_OUT
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import prices
from glyphh_server.ops.bots.goes import NO_KEY
from glyphh_server.ops.bots.runs import INTERRUPTED, now
from glyphh_server.ops.link import calls
from glyphh_server.ops.projects import final, runs, store
from glyphh_server.ops.projects.engine import now_stamp
from glyphh_server.ops.projects.results import Results
from glyphh_server.ops.projects.views import ProjectRunView

LIVE: str = "The project has a run going: answer its pull request, or cancel it, first."
NOT_WAITING: str = "That project run is not waiting on a pull request."
CANCELLED: str = "cancelled"
BEGAN: tuple[str, ...] = ("review", "turn_mode", "max_turns", "max_spend_cents")  # a run begins with its project's


class Projects(Results):
    async def get(self, org_id: uuid.UUID, run_id: uuid.UUID) -> ProjectRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await runs.get(conn, run_id)

    async def _ready(self, who: Principal, slug: str) -> tuple[Any, list[str]]:
        """The project and its crew, when a run of it can go; else refused, saying why."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            project = await store.row(conn, slug)
            if project.runs_on is not None:
                await calls.linked(conn, project.runs_on)
            await self._connected(conn, who, project)
            crew = [str(b.id) for b in await store.crew(conn, project.members)]
        if project.runs_on is None and not self.settings.anthropic_api_key and not await self.bots.own_key(who.org_id):
            raise Unavailable(NO_KEY, reason="anthropic_off")
        if not crew:
            raise Invalid("The project's crew has no bot left: add one.", reason="members")
        return project, crew

    async def _connected(self, conn: Any, who: Principal, project: Any) -> None:
        """GitHub for the project's repo: the installation of Glyphh's App that covers it now (not found, with the
        install link, when none does), connected by this person when it is not the one the project has."""
        repo = store.repo(project.repo_url)
        if await self.github.app().covering(repo) != project.github_installation_id:
            found = await self.github.connect(conn, who.user_id, repo)
            await conn.execute(update(Project).where(Project.id == project.id).values(github_installation_id=found))

    async def start(
        self, who: Principal, slug: str, task: str, model: Any = None, effort: Any = None
    ) -> ProjectRunView:
        project, crew = await self._ready(who, slug)
        stamp, cloud = now_stamp(), project.runs_on is None
        values = {"org_id": who.org_id, "project_id": project.id, "user_id": who.user_id, "task": task.strip()}
        values |= {"model": prices.model(model).id if model else None, "effort": effort}
        values |= {"members": crew, "rrotor_id": project.runs_on, "stamp": stamp, "on_cloud": cloud}
        values |= {k: getattr(project, k) for k in BEGAN}
        values["work_branch"] = final.work_branch(project.slug, stamp) if project.review == "end" else None
        try:
            async with self.engine.begin() as conn:
                await tenancy.enter(conn, who.org_id)
                made = ProjectRun.__table__.insert().values(**values).returning(ProjectRun.id)
                run_id = (await conn.execute(made)).scalar_one()
                run = await runs.row(conn, run_id)
        except IntegrityError as err:
            raise Conflict(LIVE, slug=slug) from err
        try:
            if run.work_branch:
                await final.begin(self, run)
            await self.next(who.org_id, run_id)
        except GlyphhError as err:
            await self.end(who.org_id, run_id, "failed", err.message)
        return await self.get(who.org_id, run_id)

    async def answer(self, who: Principal, run_id: uuid.UUID, answer: str) -> ProjectRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            run = await runs.row(conn, run_id)
            turn = await runs.open_turn(conn, run_id)
        if run.status != "needs_input" or (turn is None and not run.pr_url):
            raise Conflict(NOT_WAITING, run_id=str(run_id))
        if turn is None:
            await final.answer(self, run, answer)
        else:
            await self.review(run, turn, answer)
        return await self.get(who.org_id, run_id)

    async def cancel(self, who: Principal, run_id: uuid.UUID) -> ProjectRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            run = await runs.row(conn, run_id)
            out = [t for t in await runs.turns(conn, run_id) if t.status in TURN_OUT]
        if run.status not in ("running", "needs_input"):
            raise Conflict("That project run has ended.", run_id=str(run_id))
        if (task := self.tasks.get(run_id)) is not None:
            task.cancel()
        for t in out if not run.on_cloud else []:
            await calls.cancel(self.hub, run.rrotor_id, t.call_id)
        await self.end(who.org_id, run_id, "failed", CANCELLED, turn="cancelled")
        return await self.get(who.org_id, run_id)

    async def recover(self, here: str) -> int:
        """This machine's runs on Glyphh cloud cut off by its restart, failed (with no org entered: every org's). One
        waiting on the person is not cut off, nor is one on a rrotor."""
        async with self.engine.begin() as conn:
            mine = (ProjectRun.machine == here, ProjectRun.on_cloud, ProjectRun.status == "running")
            ended = {"status": "failed", "error": INTERRUPTED, "finished_at": now()}
            cut = list(await conn.execute(update(ProjectRun).where(*mine).values(**ended).returning(ProjectRun.id)))
            out = (ProjectTurn.run_id.in_([r.id for r in cut]), ProjectTurn.status.in_(TURN_OUT))
            await conn.execute(update(ProjectTurn).where(*out).values(**ended))
        return len(cut)

    async def wait(self) -> None:
        """Every step started here on Glyphh cloud, finished (the tests')."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
            await asyncio.sleep(0)

    async def close(self) -> None:
        for task in list(self.tasks.values()):
            task.cancel()
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
