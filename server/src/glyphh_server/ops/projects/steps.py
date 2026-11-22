"""A project's steps, sent where its run runs (docs/specs/bots.md, 10): a bot's `turn` and the orchestrator's `pick`,
each told the words ops/projects/turns.py has (the project's instructions, the file in the repo that holds more, the
person's task, what has been said). On a rrotor, a call of its built-in glyphh_swarm over the link (Claude Code in a
checkout, a GitHub token of the Glyphh GitHub App for that call); on Glyphh cloud, a task of this process
(ops/projects/cloud.py: the repo through GitHub's API, no code run). A server bot's card for the words: its name,
they/them, its summary as its task and its agent's prompt as its personality; its look in words from its cat."""

import asyncio
import logging
import uuid
from typing import Any

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import ProjectTurn
from glyphh_server.ops.bots import prices
from glyphh_server.ops.bots.runs import machine
from glyphh_server.ops.link import calls
from glyphh_server.ops.projects import cloud, turns
from glyphh_server.ops.projects.engine import Engine
from glyphh_server.ops.projects.store import repo

log = logging.getLogger("glyphh.projects")
PROGRAM: str = "glyphh_swarm"  # rrotor's built-in keeps its name: rrotors in the field know it by it
PLACE: str = "The project's rrotor"
ORCHESTRATOR: str = "Orchestrator"
LOOK: tuple[str, ...] = ("head", "eye", "tail", "extra", "accessory")


def card(bot: Any) -> dict[str, str]:
    return {"name": bot.name, "pronouns": "they/them", "task": bot.summary or bot.name, "personality": bot.instructions}


def look(bot: Any) -> str:
    return ", ".join(str(bot.look[k]).lower() for k in LOOK if bot.look.get(k)) or "plain"


def about(run: Any, taken: list[Any], crew: list[Any], ids: bool = False) -> str:
    """The brief every step begins with: the instructions, the task, the crew, what has been said."""
    said = [{"role": "bot", "bot_id": t.bot_slug, "text": t.said} for t in taken if t.bot_slug]
    heard = turns.transcript(said, {b.slug: b.name for b in crew})
    project = {"instructions": run.instructions, "path": run.instructions_path, "task": run.task}
    return turns.brief(project, [card(b) | ({"id": b.slug} if ids else {}) for b in crew], heard)


class Steps(Engine):
    async def send(self, run: Any, call_id: uuid.UUID, function: str, inputs: dict[str, Any]) -> None:
        """One call of glyphh_swarm on the run's rrotor, handed a GitHub token minted for this call alone (the
        project's repo, one hour: its clone, push and pull request); the run failed, saying why, when it cannot go."""
        try:
            name = repo(run.repo_url)
            token = await self.github.token(run.github_installation_id, name)
            inputs = {**inputs, "repo": name, "github_token": token}
            calls.fits(inputs, "The turn")
            if not await calls.call(self.hub, run.rrotor_id, call_id, PROGRAM, function, inputs):
                await self.end(run.org_id, run.id, "failed", calls.offline(PLACE))
        except GlyphhError as err:
            await self.end(run.org_id, run.id, "failed", err.message)

    async def step(
        self, run: Any, turn_id: uuid.UUID, call_id: uuid.UUID, function: str, inputs: dict[str, Any]
    ) -> None:
        if not run.on_cloud:
            await self.send(run, call_id, function, inputs)
            return
        await self.put_run(run.org_id, run.id, machine=machine())
        task = asyncio.create_task(self._cloud(run, turn_id, function, inputs))
        self.tasks[run.id] = task
        task.add_done_callback(lambda t: self.tasks.pop(run.id, None) if self.tasks.get(run.id) is t else None)

    async def _cloud(self, run: Any, turn_id: uuid.UUID, function: str, inputs: dict[str, Any]) -> None:
        """The step on Glyphh cloud, its result kept as a rrotor's is."""
        try:
            result = {"status": "done", "data": await cloud.STEPS[function](self, run, inputs)}
        except GlyphhError as err:
            result = {"status": "failed", "data": {"reason": err.message}}
        except Exception as err:
            log.exception("project step failed", extra={"run_id": str(run.id)})
            result = {"status": "failed", "data": {"reason": f"{type(err).__name__}: {err}"}}
        await self.took(run.org_id, turn_id, result)  # type: ignore[attr-defined]

    async def _row(self, org_id: uuid.UUID, turn_id: uuid.UUID | None, values: dict[str, Any]) -> uuid.UUID:
        """The turn's row: made, or the orchestrator's pick become the bot's turn."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            table = ProjectTurn.__table__
            if turn_id is None:
                made = table.insert().values(org_id=org_id, **values).returning(ProjectTurn.id)
                return uuid.UUID(str((await conn.execute(made)).scalar_one()))
            await conn.execute(table.update().where(ProjectTurn.id == turn_id).values(**values))
            return turn_id

    async def turn(
        self, run: Any, taken: list[Any], crew: list[Any], bot: Any, picking: Any = None, why: str = ""
    ) -> None:
        """A bot's turn: its branch, its words, sent. `picking`: the orchestrator's pick that chose it (`why`), whose
        row becomes the turn's; what the orchestrator said is kept for a run on Glyphh cloud only."""
        n = picking.n if picking is not None else len(taken) + 1
        branch, call_id = turns.branch_name(n, bot.slug, run.stamp), uuid.uuid4()
        prompt = turns.turn_prompt(card(bot), about(run, taken, crew), branch, n, why, by_tools=run.on_cloud)
        values = {"run_id": run.id, "n": n, "bot_id": bot.id, "bot_slug": bot.slug, "bot_name": bot.name}
        values |= {"branch": branch, "call_id": call_id, "status": "running", "remote_seq": 0}
        values |= {"picked_by": "orchestrator" if why else "wait", "why": why if run.on_cloud else ""}
        turn_id = await self._row(run.org_id, picking.id if picking is not None else None, values)
        inputs = {"base": run.work_branch or run.base_branch, "branch": branch, "prompt": prompt}
        inputs |= {"persona": turns.persona(card(bot), look(bot)), "model": run.model or bot.model}
        await self.step(run, turn_id, call_id, "turn", inputs | {"bot_id": bot.slug, "bot_name": bot.name})

    async def pick(self, run: Any, taken: list[Any], crew: list[Any]) -> None:
        """The orchestrator asked who goes next: a bot of the crew in its own voice, or Claude."""
        n, call_id = len(taken) + 1, uuid.uuid4()
        lead = next((b for b in crew if b.id == run.orchestrator), None)
        values = {"run_id": run.id, "n": n, "bot_slug": "", "bot_name": ORCHESTRATOR, "branch": ""}
        values |= {"call_id": call_id, "status": "picking", "picked_by": "orchestrator"}
        turn_id = await self._row(run.org_id, None, values)
        inputs = {"base": run.work_branch or run.base_branch}
        inputs["prompt"] = turns.pick_prompt(about(run, taken, crew, ids=True), n, by_tools=run.on_cloud)
        inputs["persona"] = turns.persona(card(lead), look(lead)) if lead else ""
        inputs["model"] = run.model or (lead.model if lead else prices.DEFAULT)
        await self.step(run, turn_id, call_id, "pick", inputs)
