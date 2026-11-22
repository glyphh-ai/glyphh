"""A project's run going on (docs/specs/bots.md, 10): nothing waits here; each step's result moves the run on
(`next`). There is no order and there are no rounds: the run ends when the crew is done (two bots in a row said DONE,
or the whole crew in a row had nothing to do: ops/projects/turns.py), when its orchestrator says so, or at a safety
cap (its turns, or what their tokens cost); else the next turn is taken, wait your turn or by the orchestrator's pick
(ops/projects/steps.py). The bots are read again at each turn, so an edit made while the project runs is picked up; a
bot of the crew deleted since ends the run."""

import asyncio
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import select, update

from glyphh_server.db import tenancy
from glyphh_server.errors import Unavailable
from glyphh_server.llm import meter
from glyphh_server.models import Bot, ProjectRun, ProjectTurn
from glyphh_server.models.project import TURN_OUT
from glyphh_server.ops.bots import prices
from glyphh_server.ops.bots.goes import NO_KEY
from glyphh_server.ops.bots.runs import now
from glyphh_server.ops.github_app import load_key
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.projects import final, runs, store, turns
from glyphh_server.ops.projects.claude import Claude
from glyphh_server.ops.projects.github import GitHub
from glyphh_server.ops.projects.repo import Repo

GONE: str = "A bot of the crew was deleted: the project cannot go on."
MICROS_PER_CENT: int = 10_000


def now_stamp() -> str:
    return turns.stamp(int(time.time() * 1000))


class Engine:
    def __init__(self, bots: Any, hub: Hub, http: httpx.AsyncClient) -> None:
        self.bots, self.engine, self.settings, self.hub, self.http = bots, bots.engine, bots.settings, hub, http
        self.tasks: dict[uuid.UUID, asyncio.Task[None]] = {}  # a run's step on Glyphh cloud
        self.github = GitHub(http, self.settings, load_key(self.settings))  # the Glyphh GitHub App: a turn's token
        self.repo_for: Any = lambda token, repo: Repo(http, token, repo)  # the repo by GitHub's API (a test's fake)
        self.claude_for: Any = Claude  # Claude with tools, by key and model (a test sets a fake)

    async def put_run(self, org_id: uuid.UUID, run_id: uuid.UUID, **values: Any) -> None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(update(ProjectRun).where(ProjectRun.id == run_id).values(**values))

    async def put_turn(self, org_id: uuid.UUID, turn_id: uuid.UUID, **values: Any) -> None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(update(ProjectTurn).where(ProjectTurn.id == turn_id).values(**values))

    async def end(self, org_id: uuid.UUID, run_id: uuid.UUID, status: str, error: str = "", **over: str) -> None:
        """The run ended (`ended`: why a done one did); a turn of it still out ended too (`turn`: failed, or
        cancelled)."""
        ended = {"ended": over["ended"]} if "ended" in over else {}
        await self.put_run(org_id, run_id, status=status, error=error, finished_at=now(), **ended)
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            out = (ProjectTurn.run_id == run_id, ProjectTurn.status.in_(TURN_OUT))
            values = {"status": over.get("turn", "failed"), "error": error, "finished_at": now()}
            await conn.execute(update(ProjectTurn).where(*out).values(**values))

    async def repo_of(self, run: Any) -> Any:
        """The run's repo through GitHub's API, with a token minted now for it alone (one hour)."""
        repo = store.repo(run.repo_url)
        return self.repo_for(await self.github.token(run.github_installation_id, repo), repo)

    async def claude_of(self, org_id: uuid.UUID, model: str) -> tuple[Any, Any]:
        """Claude for a step on Glyphh cloud, on the org's own key or Glyphh's, and its meter: the step let in once
        (its first request: the plan's allowance, then the balance), then each request's tokens charged (the markup
        alone on the org's own key)."""
        own = await self.bots.own_key(org_id)
        if not own and not self.settings.anthropic_api_key:
            raise Unavailable(NO_KEY, reason="anthropic_off")
        priced = prices.charged(model, own_key=bool(own))
        let_in: list[Any] = []

        async def metered(ask: Any) -> Any:
            if not let_in:
                let_in.append(await meter.admit(self.engine, self.bots.redis, self.settings, org_id))
            got = await ask()
            await meter.record(self.engine, let_in[0], priced, got.usage.input_tokens, got.usage.output_tokens)
            return got

        return self.claude_for(own or self.settings.anthropic_api_key, model), metered

    async def used(self, run: Any, turn: Any, usage: Any) -> None:
        """A step's tokens added to its turn, and what they cost at Anthropic's rate (the spend cap counts it)."""
        usage = usage if isinstance(usage, dict) else {}
        spent = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, run.org_id)
            by = turn.bot_id or run.orchestrator
            own = (await conn.execute(select(Bot.model).where(Bot.id == by))).scalar()
            model = run.model or own or prices.DEFAULT
            more = {
                "input_tokens": ProjectTurn.input_tokens + spent[0],
                "output_tokens": ProjectTurn.output_tokens + spent[1],
                "cost_micros": ProjectTurn.cost_micros + prices.model(model).cost_micros(*spent),
            }
            await conn.execute(update(ProjectTurn).where(ProjectTurn.id == turn.id).values(**more))

    async def standing(self, org_id: uuid.UUID, run_id: uuid.UUID) -> tuple[Any, list[Any], list[Any]] | None:
        """The run, its turns so far and its crew as they are now; None once a bot of the crew is gone (the run
        ended, saying so)."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            run = await runs.row(conn, run_id)
            taken = await runs.turns(conn, run_id)
            crew = await store.crew(conn, run.members)
        if len(crew) < len(run.members):
            await self.end(org_id, run_id, "failed", GONE)
            return None
        return run, taken, crew

    def over(self, run: Any, taken: list[Any], row: list[tuple[str, bool]]) -> str:
        """Why the run is over, if it is: the crew is done, or a safety cap."""
        if turns.crew_done(row, len(run.members)):
            return "done"
        if len(taken) >= run.max_turns:
            return "max_turns"
        spent = sum(t.cost_micros for t in taken)
        return "max_spend" if run.max_spend_cents and spent >= run.max_spend_cents * MICROS_PER_CENT else ""

    async def next(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """The next turn, or the run's end."""
        if (found := await self.standing(org_id, run_id)) is None:
            return
        run, taken, crew = found
        row = turns.idle_row(runs.went(taken))
        await self.put_run(org_id, run_id, done=[bot for bot, _ in row])
        if why := self.over(run, taken, row):
            await final.finish(self, run, taken, why)
        elif run.turn_mode == "orchestrator":
            await self.pick(run, taken, crew)  # type: ignore[attr-defined]
        else:
            await self.turn(run, taken, crew, self.waiting(taken, crew, row))  # type: ignore[attr-defined]

    def waiting(self, taken: list[Any], crew: list[Any], row: list[tuple[str, bool]]) -> Any:
        """Wait your turn: the bot of the crew that goes next."""
        slugs = [b.slug for b in crew]
        chosen = turns.next_up(slugs, [t["bot"] for t in runs.went(taken)], [bot for bot, _ in row]) or slugs[0]
        return next(b for b in crew if b.slug == chosen)
