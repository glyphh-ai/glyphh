"""A bot's runs on the org's rrotor it is set to run on (bots.runs_on; docs/specs/bot-agent-loop.md, 6.2): the server
keeps the bot, its decisions and its runs, the rrotor runs the turn (its built-in glyphh_bot's `agent`, rrotor
0.9.0). Started (by the person or its schedule), the run is refused unless that rrotor is linked now and the org's
tokens are not spent; then it is sent there as a `call` (ops/link/calls.py) and is `dispatched` until its result
comes back (ops/bots/remote_out.py). The rrotor calls every tool that lives here at the run's tool endpoint
(ops/bots/tool_calls.py), where the bot's permissions and Ada's decisions are held, so a question is asked by this
server and waits as any run's does; answered within the 14 minutes the rrotor still holds the run, the answer goes
as `continue`; later, as a fresh call that resumes the session the rrotor kept. Cancelled, a run is ended here and
the rrotor is told. Anything that keeps a call from going fails the run, saying why.

Each call carries the folders of the machine the bot's owner chose (ops/bots/access.py): the rrotor gives the run
exactly those, with its own file tools over them, and refuses the call, in a plain sentence that becomes the run's
error, when its own owner does not offer one of them."""

import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, update

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, GlyphhError, Invalid
from glyphh_server.llm import meter
from glyphh_server.models import BotRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import approvals, mend, orchestrator, places, remote_in, runs
from glyphh_server.ops.bots.agent import carry, prompt
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent.desk import Ask
from glyphh_server.ops.bots.goes import Goes
from glyphh_server.ops.bots.views import RunView
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.hub import Hub

PROGRAM: str = "glyphh_bot"
FUNCTION: str = "agent"
RROTOR_MIN: tuple[int, int] = (0, 9)  # the first rrotor whose glyphh_bot runs a bot as an agent
HELD: timedelta = timedelta(minutes=14)  # a rrotor holds a waiting run 15 minutes: past 14, a fresh call
PLACE: str = "The bot's rrotor"
CANCELLED: str = "cancelled"
OLD: str = "{name} runs rrotor {version}, which cannot run this bot: update it to rrotor 0.9.0 or later."


def runs_agents(version: str | None) -> bool:
    found = re.match(r"(\d+)\.(\d+)", version or "")
    return found is not None and (int(found[1]), int(found[2])) >= RROTOR_MIN


class Remote:
    def __init__(self, svc: Goes, hub: Hub) -> None:
        self.svc, self.hub = svc, hub

    async def get(self, org_id: uuid.UUID, run_id: uuid.UUID) -> RunView:
        async with self.svc.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await runs.get(conn, run_id)

    async def start(self, bot: Any, user_id: uuid.UUID | None, given: str) -> RunView:
        """A run of the bot on its rrotor: refused while the rrotor is offline or the org's tokens are spent."""
        async with self.svc.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            await calls.linked(conn, bot.runs_on)
        await meter.admit(self.svc.engine, self.svc.redis, self.svc.settings, bot.org_id)
        made = await runs.create(self.svc.engine, bot.org_id, bot, user_id, given)
        await self.send(bot.org_id, made.id, bot.id, bot.runs_on, prompt.task(bot, given), False)
        return await self.get(bot.org_id, made.id)

    async def send(
        self, org_id: uuid.UUID, run_id: uuid.UUID, bot_id: uuid.UUID, rrotor_id: uuid.UUID, message: str, resume: bool
    ) -> None:
        """One call of glyphh_bot's agent for the run: its inputs made, the run dispatched, the call sent (the run
        failed, saying why, when it cannot go). The rrotor counts the run's tokens through every call of it (it
        keeps the count with the session), so they are counted from what the run had at its first call."""
        try:
            bot = await self.svc.bot(org_id, bot_id)
            async with self.svc.engine.begin() as conn:
                await tenancy.enter(conn, org_id)
                place = await places.one(conn, rrotor_id)
            if not runs_agents(place.version):
                raise Invalid(OLD.format(name=place.name, version=place.version or "an earlier version"))
            more = orchestrator.tools(self.svc, bot, None)
            run, desk, found = await agent_run.prepared(self.svc, bot, run_id, more)
            turn = agent_run.turn(bot, run, desk, found, message, here=False)
            turn.session = "resume" if resume else ""
            sent = remote_in.inputs(self.svc.settings, org_id, run_id, turn, found)
            sent["limits"]["tokens"] = agent_run.limits(bot)["tokens"]
            if bot.folders:
                sent["file_tools"] = True
            calls.fits(sent, "The bot's plugins and tools")
            had = run.remote if resume else {}
            began = {
                "in": had.get("in", run.input_tokens),
                "out": had.get("out", run.output_tokens),
                "message": message,
            }
            dispatched = {"status": "dispatched", "rrotor_id": rrotor_id, "own_key": True, "question": {}}
            started = func.coalesce(BotRun.started_at, func.now())
            await runs.put(self.svc.engine, org_id, run_id, **dispatched, remote=began, started_at=started)
            if not await calls.call(self.hub, rrotor_id, run_id, PROGRAM, FUNCTION, sent, bot.folders):
                await runs.failed(self.svc.engine, org_id, run_id, calls.offline(PLACE))
        except GlyphhError as err:
            await runs.failed(self.svc.engine, org_id, run_id, err.message)

    async def _carried(self, who: Principal, bot: Any, found: Any, answer: Any) -> str:
        """The answer taken where it belongs, and the words the rrotor's session resumes with. A yes to a change of
        a file is kept as the yes to that change (ops/bots/approvals.py), for the rrotor's `file_change` to take."""
        if found.question.get("file"):
            yes = approvals.granted_file(found.question, answer, who.user_id)
            await runs.put(self.svc.engine, who.org_id, found.id, approvals=yes)
            return prompt.approved(found.question, str(answer))
        return await carry.on(self.svc, bot, found.id, dict(found.question), answer, who.user_id)

    async def answer(self, who: Principal, found: Any, answer: Any) -> RunView:
        """The waiting run carried on with the person's answer (already fitted to its question)."""
        bot = await self.svc.bot(who.org_id, found.bot_id)
        async with self.svc.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            moved = (
                update(BotRun)
                .where(BotRun.id == found.id, BotRun.status == "needs_input")
                .values(status="dispatched", question={})
            )
            if (await conn.execute(moved)).rowcount != 1:
                raise Conflict(mend.NOT_WAITING, run_id=str(found.id))
        try:
            message = await self._carried(who, bot, found, answer)
        except Ask as ask:  # the orchestrator's: the bot it asked asks again
            await runs.put(self.svc.engine, who.org_id, found.id, status="needs_input", question=ask.question)
            return await self.get(who.org_id, found.id)
        await runs.put(self.svc.engine, who.org_id, found.id, remote={**found.remote, "message": message})
        if held(found.remote):
            if not await calls.carry_on(self.hub, found.rrotor_id, found.id, message):
                await runs.failed(self.svc.engine, who.org_id, found.id, calls.offline(PLACE))
        else:
            await self.send(who.org_id, found.id, found.bot_id, found.rrotor_id, message, True)
        return await self.get(who.org_id, found.id)

    async def cancel(self, who: Principal, found: Any) -> RunView:
        """A run out on the rrotor, ended here and stopped there (best effort: an offline rrotor's ends itself)."""
        await calls.cancel(self.hub, found.rrotor_id, found.id)
        await runs.failed(self.svc.engine, who.org_id, found.id, CANCELLED)
        return await self.get(who.org_id, found.id)

    async def drop(self, found: Any) -> None:
        """A waiting run cancelled here: the rrotor's run that still waits for it, ended too."""
        if held(found.remote):
            await calls.cancel(self.hub, found.rrotor_id, found.id)


def held(remote: dict[str, Any]) -> bool:
    """Whether the rrotor still holds the run's wait: it began under HELD ago and has not expired there."""
    since = remote.get("since")
    return bool(since) and datetime.fromisoformat(since) > runs.now() - HELD
