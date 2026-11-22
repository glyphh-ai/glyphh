"""A swarm's run, as Glyphh Bot's `swarm()` runs one (glyphh-bot, src/renderer/src/engine.ts), on the server: for each
round and each bot of the crew in order, a turn on the swarm's rrotor (glyphh_swarm's `turn`: a fresh branch off
the base, Claude Code doing the bot's part, committed as the bot and opened as a pull request), told the words
ops/swarms/turns.py has. Nothing waits here: each turn is a call over the link, and its result (ops/swarms/service.py)
moves the run on: an open pull request waits for the person (review each_turn) or is merged at once (auto), then the
DONE rule, then the next bot's turn or the run's end. The bots are read again at each turn, so an edit made while the
swarm runs is picked up; a bot of the crew deleted since ends the run. A server bot's card for the words: its name,
they/them, its summary as its task and its agent's prompt as its personality; its look in words from its cat."""

import time
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import Bot, SwarmRun, SwarmTurn
from glyphh_server.ops.bots.runs import now
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.swarms import github, runs, turns
from glyphh_server.ops.swarms.store import repo

PROGRAM: str = "glyphh_swarm"
PLACE: str = "The swarm's rrotor"
LOOK: tuple[str, ...] = ("head", "eye", "tail", "extra", "accessory")
OUT: tuple[str, ...] = ("running", "merging", "rejecting")  # a turn whose call is out on the rrotor


def card(bot: Any) -> dict[str, str]:
    return {"name": bot.name, "pronouns": "they/them", "task": bot.summary or bot.name, "personality": bot.instructions}


def look(bot: Any) -> str:
    return ", ".join(str(bot.look[k]).lower() for k in LOOK if bot.look.get(k)) or "plain"


def now_stamp() -> str:
    return turns.stamp(int(time.time() * 1000))


class Engine:
    def __init__(self, engine: AsyncEngine, settings: Settings, hub: Hub) -> None:
        self.engine, self.settings, self.hub = engine, settings, hub

    async def put_run(self, org_id: uuid.UUID, run_id: uuid.UUID, **values: Any) -> None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(update(SwarmRun).where(SwarmRun.id == run_id).values(**values))

    async def put_turn(self, org_id: uuid.UUID, turn_id: uuid.UUID, **values: Any) -> None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(update(SwarmTurn).where(SwarmTurn.id == turn_id).values(**values))

    async def end(
        self, org_id: uuid.UUID, run_id: uuid.UUID, status: str, error: str = "", turn: str = "failed"
    ) -> None:
        """The run ended; a turn of it still out on the rrotor ended too (`turn`: failed, or cancelled)."""
        await self.put_run(org_id, run_id, status=status, error=error, finished_at=now())
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            out = (SwarmTurn.run_id == run_id, SwarmTurn.status.in_(OUT))
            await conn.execute(update(SwarmTurn).where(*out).values(status=turn, error=error, finished_at=now()))

    async def send(
        self, org_id: uuid.UUID, run: Any, call_id: uuid.UUID, function: str, inputs: dict[str, Any]
    ) -> None:
        """One call of glyphh_swarm on the run's rrotor (the org's GitHub token added); the run failed, saying why,
        when it cannot go."""
        try:
            async with self.engine.begin() as conn:
                await tenancy.enter(conn, org_id)
                inputs = {**inputs, "repo": repo(run.repo_url), "github_token": await github.token(conn, self.secret)}
            calls.fits(inputs, "The turn")
            if not await calls.call(self.hub, run.rrotor_id, call_id, PROGRAM, function, inputs):
                await self.end(org_id, run.id, "failed", calls.offline(PLACE))
        except GlyphhError as err:
            await self.end(org_id, run.id, "failed", err.message)

    @property
    def secret(self) -> str:
        return self.settings.secret_key

    async def next(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """The next bot's turn, or the run's end once every round is taken."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            run = await runs.row(conn, run_id)
            taken = await runs.turns(conn, run_id)
            ids = [uuid.UUID(i) for i in run.members]
            bots = {str(b.id): b for b in await conn.execute(select(Bot).where(Bot.id.in_(ids)))}
        n, size = len(taken) + 1, len(run.members)
        if n > run.rounds * size:
            await self.end(org_id, run_id, "done")
            return
        index, round_ = (n - 1) % size, (n - 1) // size + 1
        crew = [bots.get(i) for i in run.members]
        if any(b is None for b in crew):
            await self.end(org_id, run_id, "failed", "A bot of the crew was deleted: the swarm cannot go on.")
            return
        await self._turn(org_id, run, taken, crew, (n, index, round_))

    async def _turn(
        self, org_id: uuid.UUID, run: Any, taken: list[Any], crew: list[Any], at: tuple[int, int, int]
    ) -> None:
        n, index, round_ = at
        bot = crew[index]
        branch = turns.branch_name(n, bot.slug, run.stamp)
        said = [{"role": "user", "text": run.task}] + [
            {"role": "bot", "bot_id": t.bot_slug, "text": t.said} for t in taken
        ]
        heard = turns.transcript(said, {b.slug: b.name for b in crew})
        last = round_ == run.rounds and index == len(crew) - 1
        prompt = turns.turn_prompt(card(bot), [card(b) for b in crew], run.task, heard, branch, n, last)
        call_id = uuid.uuid4()
        values = {"org_id": org_id, "run_id": run.id, "n": n, "round": round_, "bot_id": bot.id, "branch": branch}
        values |= {"bot_slug": bot.slug, "bot_name": bot.name, "call_id": call_id}
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(SwarmTurn.__table__.insert().values(**values))
        inputs = {
            "base": run.base_branch,
            "branch": branch,
            "prompt": prompt,
            "persona": turns.persona(card(bot), look(bot)),
        }
        inputs |= {"model": bot.model, "bot_id": bot.slug, "bot_name": bot.name}
        await self.send(org_id, run, call_id, "turn", inputs)
