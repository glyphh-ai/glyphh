"""A bot's runs on the org's rrotor it is set to run on (bots.runs_on; docs/specs/bots.md, 9): the server keeps the
bot, its state and its runs, the rrotor runs it (its built-in glyphh_bot). Started (by the person or its schedule),
the run is refused unless that rrotor is linked now and the org's tokens are not spent; then it is sent there as a
`call` (ops/link/calls.py) and is `dispatched` until its result comes back (ops/bots/remote_out.py). A question
waits in the approvals queue as any run's does; answered within the 14 minutes the rrotor still holds the run, the
answer goes as `continue`; later, as a fresh call carrying the bot's state and the answer. Cancelled, a run is ended
here and the rrotor is told. Anything that keeps a call from going fails the run, saying why.

Each call carries the folders of the machine the bot's owner chose (ops/bots/access.py): the rrotor gives the run
exactly those and refuses the call, in a plain sentence that becomes the run's error, when its own owner does not
offer one of them. A rrotor before 0.6.0 knows no folders (a bot with any is not sent there: the run fails saying to
update it) and no effort (left out for it). A rrotor from 0.8.0 is also told to give the bot's agent steps those
folders' files (`file_tools`, ops/bots/files.py); one before it keeps the single request a step was."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, update

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, GlyphhError, Invalid
from glyphh_server.llm import meter
from glyphh_server.models import BotRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import access, approvals, cloud, files, mend, places, remote_in, runs
from glyphh_server.ops.bots.goes import Goes
from glyphh_server.ops.bots.views import RunView
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.hub import Hub

PROGRAM: str = "glyphh_bot"
FUNCTION: str = "run"
HELD: timedelta = timedelta(minutes=14)  # a rrotor holds a waiting run 15 minutes: past 14, a fresh call
PLACE: str = "The bot's rrotor"
CANCELLED: str = "cancelled"
OLD: str = (
    "{name} runs rrotor {version}, which cannot give a bot folders: update it to rrotor "
    + access.RROTOR_MIN_NAME
    + " or later, or take the folders off the bot."
)


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
        await self.send(bot.org_id, made.id, bot.id, bot.runs_on, given or None, None)
        return await self.get(bot.org_id, made.id)

    async def send(
        self, org_id: uuid.UUID, run_id: uuid.UUID, bot_id: uuid.UUID, rrotor_id: uuid.UUID, given: Any, answer: Any
    ) -> None:
        """One call of glyphh_bot for the run: its inputs made, the run dispatched, the call sent (the run failed,
        saying why, when it cannot go). The call's tokens are counted from what the run had."""
        try:
            bot = await self.svc.bot(org_id, bot_id)
            async with self.svc.engine.begin() as conn:
                await tenancy.enter(conn, org_id)
                _, asked = await cloud.calls(self.svc.pd, conn, bot)
                run = await runs.row(conn, run_id)
                place = await places.one(conn, rrotor_id)
            knows = access.takes(place.version)  # folders and effort: rrotor 0.6.0's
            if bot.folders and not knows:
                raise Invalid(OLD.format(name=place.name, version=place.version or "an earlier version"))
            # its folders' files as its agent steps' tools: rrotor 0.8.0's (an older one keeps the single request),
            # which also puts what the person typed to those steps, so a fresh call for an answer carries it again
            with_files = bool(bot.folders) and files.uses(place.version)
            task = given or (run.input or None if with_files else None)
            guarded = cloud.guarded(bot, asked)
            more = {"effort": knows, "file_tools": with_files}
            sent = remote_in.inputs(self.svc.settings, guarded, run_id, task, answer, **more)
            calls.fits(sent, "The bot's package and state")
            began = {"in": run.input_tokens, "out": run.output_tokens, "answer": answer}
            dispatched = {"status": "dispatched", "rrotor_id": rrotor_id, "own_key": True, "question": {}}
            started = func.coalesce(BotRun.started_at, func.now())
            await runs.put(self.svc.engine, org_id, run_id, **dispatched, remote=began, started_at=started)
            if not await calls.call(self.hub, rrotor_id, run_id, PROGRAM, FUNCTION, sent, bot.folders):
                await runs.failed(self.svc.engine, org_id, run_id, calls.offline(PLACE))
        except GlyphhError as err:
            await runs.failed(self.svc.engine, org_id, run_id, err.message)

    async def answer(self, who: Principal, found: Any, answer: Any) -> RunView:
        """The waiting run carried on with the person's answer (already fitted to its question); their yes to an
        approval kept here, by the tool its step runs, for the rrotor's call of it to take (ops/bots/approvals.py)."""
        remote = {**found.remote, "answer": answer}
        bot = await self.svc.bot(who.org_id, found.bot_id)
        yes = approvals.granted(found.question, bot.spec, answer, who.user_id)
        async with self.svc.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            moved = (
                update(BotRun)
                .where(BotRun.id == found.id, BotRun.status == "needs_input")
                .values(status="dispatched", question={}, remote=remote, approvals=yes)
            )
            if (await conn.execute(moved)).rowcount != 1:
                raise Conflict(mend.NOT_WAITING, run_id=str(found.id))
        if held(found.remote):
            if not await calls.carry_on(self.hub, found.rrotor_id, found.id, answer):
                await runs.failed(self.svc.engine, who.org_id, found.id, calls.offline(PLACE))
        else:
            await self.send(who.org_id, found.id, found.bot_id, found.rrotor_id, None, answer)
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
