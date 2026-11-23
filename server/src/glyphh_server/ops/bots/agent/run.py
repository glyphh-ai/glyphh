"""One go of a bot's run on Glyphh cloud (docs/specs/bot-agent-loop.md, 2): the bot's agent given the person's
message (or, carried on, what they answered), its tools at the desk, its plugins in the run's own folder, on the
org's own Anthropic key or Glyphh's. The go is let in by the meter and its tokens charged after, whatever its end:
the agent's final words (done), a question for the person (needs_input, its session kept for the answer), or a
failure. A run's tokens over the bot's limit fail it."""

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from glyphh.bots import BotError
from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.llm import meter
from glyphh_server.models import BotRun
from glyphh_server.ops.bots import access, fetching, prices, runs
from glyphh_server.ops.bots.agent import plugins, prompt, session, tools
from glyphh_server.ops.bots.agent.desk import STEPS, Desk
from glyphh_server.ops.bots.agent.turn import Ended, Turn

FOLDERS: Path = Path(tempfile.gettempdir()) / "glyphh-bot-runs"
OUTPUT_MAX: int = 50_000
LIMITS: dict[str, int] = {"turns": 25, "seconds": 300, "tokens": 400_000, "runs_per_day": 200}
OVER: str = "It used more than a run may ({most:,} tokens) and was stopped: ask for less at once."
SILENT: str = "It finished without saying anything."


def limits(bot: Any) -> dict[str, int]:
    """The bot's limits: its own where it sets one (a whole number above zero), else the defaults."""
    own = bot.spec.get("limits") if isinstance(bot.spec.get("limits"), dict) else {}
    return {k: v if isinstance(v := own.get(k), int) and v > 0 else default for k, default in LIMITS.items()}


async def fetch(bot: Any, given: dict[str, Any]) -> Any:
    """`fetch`: a GET of JSON from one of the bot's hosts (ops/bots/fetching.py has the checks)."""
    return await asyncio.to_thread(fetching.fetched, bot.spec, given)


async def prepared(svc: Any, bot: Any, run_id: uuid.UUID, more: dict[str, tools.Tool]) -> tuple[Any, Desk, list[Any]]:
    """The run's row, its desk (the bot's tools, and `more`: the orchestrator's) and the bot's plugins."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        run = (await conn.execute(select(BotRun).where(BotRun.id == run_id))).one()
        own = await tools.of(svc.pd, conn, bot, lambda given: fetch(bot, given))
        found = await plugins.of(conn, bot)
    return run, Desk(svc, bot, run_id, run.loop_run, {**own, **more}), found


def turn(
    bot: Any, run: Any, desk: Desk, found: list[Any], message: str, key: str = "", store: Any = None, here: bool = True
) -> Turn:
    """The turn as the Agent SDK is handed it. `here`: on this machine, in the run's own folder, emptied, with the
    bot's plugins written into it; else it is only described (a rrotor runs it, ops/bots/remote_in.py)."""
    folder = FOLDERS / str(run.id)
    if here:
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    most = limits(bot)
    skills = [s for p in found for s in p.skills]
    return Turn(
        system=prompt.system(bot, desk.tools, skills),
        message=message,
        tools=list(desk.tools.values()),
        call=desk.call,
        allowed=desk.allowed,
        made=desk.run,
        model=bot.model,
        effort=access.effort_for(bot.model, bot.effort),
        key=key,
        folder=folder,
        store=store,
        session=run.session_id,
        turns=most["turns"],
        seconds=float(most["seconds"]),
        plugins=plugins.written(folder, found) if here else [],
        skills=skills,
    )


async def go(svc: Any, bot: Any, run_id: uuid.UUID, message: str, more: dict[str, tools.Tool]) -> None:
    """The go, and the run's row as it leaves it."""
    key, own = await svc.key_of(bot)
    admitted = await meter.admit(svc.engine, svc.redis, svc.settings, bot.org_id)
    run, desk, found = await prepared(svc, bot, run_id, more)
    most = limits(bot)["tokens"]
    if run.input_tokens + run.output_tokens > most:  # a run carried on that had used it all before it waited
        raise BotError(OVER.format(most=most))
    await runs.start(svc.engine, bot.org_id, run_id, own)
    made = turn(bot, run, desk, found, message, key, session.Sessions(svc.engine, bot.org_id, run_id))
    try:
        got: Ended = await svc.agent(made)
    finally:
        shutil.rmtree(made.folder, ignore_errors=True)
    priced = prices.charged(bot.model, own_key=own)
    charged = await meter.record(svc.engine, admitted, priced, got.input_tokens, got.output_tokens)
    await left(svc, bot, run_id, got, charged)


def _log(data: dict[str, Any]) -> list[str]:
    return [f"{s['title']}{'' if s['ok'] else ' (failed)'}" for s in data.get(STEPS, [])]


async def left(svc: Any, bot: Any, run_id: uuid.UUID, got: Ended, charged: int) -> None:
    """What the go left, on the run: only while it is still this go's (a run cancelled meanwhile stays cancelled)."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        run = (await conn.execute(select(BotRun).where(BotRun.id == run_id).with_for_update())).one()
        spent = {"input_tokens": run.input_tokens + got.input_tokens, "output_tokens": run.output_tokens}
        spent["output_tokens"] += got.output_tokens
        values: dict[str, Any] = {**spent, "cost_micros": run.cost_micros + charged, "log": _log(run.data)}
        most = limits(bot)["tokens"]
        if got.asked and run.question:
            values |= {"status": "needs_input", "session_id": got.session}
        elif got.error:
            values |= {"status": "failed", "error": got.error, "question": {}}
        elif spent["input_tokens"] + spent["output_tokens"] > most:
            values |= {"status": "failed", "error": OVER.format(most=most), "question": {}}
        else:
            values |= {"status": "done", "output": got.text[:OUTPUT_MAX], "error": "" if got.text else SILENT}
        if values["status"] != "needs_input":
            values |= {"finished_at": runs.now(), "session_id": ""}
        if run.status != "running":
            values = {k: values[k] for k in ("input_tokens", "output_tokens", "cost_micros")}
        await conn.execute(BotRun.__table__.update().where(BotRun.id == run_id).values(**values))
    if values.get("status", "needs_input") != "needs_input":
        await session.drop(svc.engine, bot.org_id, run_id)
