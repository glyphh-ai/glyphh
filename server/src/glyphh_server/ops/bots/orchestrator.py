"""The org's orchestrator (docs/specs/bot-agent-loop.md, 8): the one bot every org has, the bot a person lands on
and talks to by default and the one that runs the crew. It is a bot like the others (it can be edited: name, cat,
instructions, model, apps, schedule) but is never deleted and its role never changes. Beside any app's tools it
sees the org's bots, hands a task to one (a run of that bot, under that bot's own permission mode) and starts,
reads and stops the crew's run. A bot it asked that must ask the person stops the orchestrator's run with the same
question; the answer goes to that bot's run, and the orchestrator carries on when it ends."""

import asyncio
import contextlib
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import keys as ada_keys
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, GlyphhError
from glyphh_server.models import Bot, BotRun, Org
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import seal
from glyphh_server.ops.bots import prices
from glyphh_server.ops.bots.agent.desk import Ask
from glyphh_server.ops.bots.agent.tools import Tool
from glyphh_server.ops.bots.orchestrator_crew import crew_tools

ROLE: str = "orchestrator"
SLUGS: tuple[str, ...] = ("orchestrator", "the-orchestrator", "glyphh-orchestrator")
KEPT: str = "The orchestrator is always here: you can change it, but not delete it."
WORKING: tuple[str, ...] = ("queued", "running", "dispatched")
WAIT_SECONDS: float = 600.0
EVERY: float = 0.5
INSTRUCTIONS: str = (
    "You are the orchestrator: the bot a person talks to first. Answer simple things yourself, in a sentence or "
    "two. When the person wants work done, look at the bots with list_bots and hand the task to the bot whose job "
    "it is with ask_bot, in words that bot can act on; then tell the person what that bot answered, plainly. If no "
    "bot fits, say so and say which bots there are. When the work is for the whole crew on a code repository, "
    "start the crew with crew_start, and use crew_status and crew_stop to read or stop it."
)
DEFAULT: dict[str, Any] = {
    "name": "Orchestrator",
    "summary": "Answers you and hands work to the right bot",
    "look": {"head": "round", "tail": "curl", "eye": "calm", "extra": "none", "accessory": "headset", "pose": "sit"},
    "instructions": INSTRUCTIONS,
    "model": prices.DEFAULT,
    "role": ROLE,
    "spec": {"limits": {"seconds": 900}},
    "task": "Say which bots are here and what each is for.",
    "examples": ["What can my bots do?", "Who should handle this?", "Give the crew a task"],
}
NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}}
ASKS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bot": {"type": "string", "description": "The bot's name, as list_bots says it"},
        "task": {"type": "string", "description": "What it should do, in words it can act on"},
    },
    "required": ["bot", "task"],
}


async def ensure(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    """The org's orchestrator, made when it has none (under the first of its slugs that is free)."""
    taken = set((await conn.scalars(select(Bot.slug).where(Bot.org_id == org_id, Bot.slug.in_(SLUGS)))).all())
    slug = next((s for s in SLUGS if s not in taken), f"orchestrator-{uuid.uuid4().hex[:6]}")
    made = insert(Bot).values(org_id=org_id, slug=slug, **DEFAULT)
    one = made.on_conflict_do_nothing(index_elements=["org_id"], index_where=text("role = 'orchestrator'"))
    await conn.execute(one)


async def keyed(conn: AsyncConnection, bot: Any, secret: str) -> str:
    """The bot's sealed Ada key; one is made, as the org's admin, for a bot that has none yet (the orchestrator is
    made without: nothing that makes it can make keys)."""
    if bot.ada_key:
        return str(bot.ada_key)
    admin = (await conn.execute(select(Org.admin_user_id).where(Org.id == bot.org_id))).scalar_one()
    who = Principal(user_id=admin, org_id=bot.org_id, role="admin")
    made = await ada_keys.create(conn, who, f"bot {bot.slug}", None, 0.0)
    sealed = seal(secret, made.key)
    await conn.execute(Bot.__table__.update().where(Bot.id == bot.id).values(ada_key=sealed))
    return sealed


def refuse_delete(bot: Any) -> None:
    if bot.role == ROLE:
        raise Conflict(KEPT, reason="orchestrator", slug=bot.slug)


async def _bots(svc: Any, org_id: uuid.UUID, but: uuid.UUID) -> list[Any]:
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        return list(await conn.execute(select(Bot).where(Bot.id != but).order_by(Bot.name)))


async def settled(svc: Any, org_id: uuid.UUID, run_id: uuid.UUID) -> Any:
    """The run once it is no longer working (it ended, or waits on the person); as it is when WAIT_SECONDS pass."""
    waited = 0.0
    while True:
        async with svc.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            run = (await conn.execute(select(BotRun).where(BotRun.id == run_id))).one()
        if run.status not in WORKING or waited >= WAIT_SECONDS:
            return run
        await asyncio.sleep(EVERY)
        waited += EVERY


def heard(name: str, run: Any) -> Any:
    """What a bot's run came to, for the orchestrator: its answer; its question for the person (Ask); or why it
    failed (ValueError)."""
    if run.status == "needs_input":
        asks = {**run.question, "question": f"{name} asks: {run.question.get('question', '')}"}
        raise Ask({**asks, "child_run": str(run.id), "child_bot": name})
    if run.status in ("failed", "skipped"):
        raise ValueError(f"{name} could not do it: {run.error or 'it failed'}")
    if run.status in WORKING:
        return {"bot": name, "status": "still working", "answer": ""}
    return {"bot": name, "status": "done", "answer": run.output or run.error}


def tools(svc: Any, bot: Any, user_id: uuid.UUID | None) -> dict[str, Tool]:
    """The orchestrator's own tools; none for any other bot."""
    if bot.role != ROLE:
        return {}

    async def list_bots(given: dict[str, Any]) -> Any:
        return [{"bot": b.name, "does": b.summary} for b in await _bots(svc, bot.org_id, bot.id)]

    async def ask_bot(given: dict[str, Any]) -> Any:
        wanted = str(given.get("bot") or "").strip().lower()
        found = [b for b in await _bots(svc, bot.org_id, bot.id) if wanted in (b.name.lower(), b.slug)]
        if not found:
            raise ValueError(f"There is no bot {given.get('bot')!r}: list_bots says which there are.")
        try:
            made = await svc.queued(found[0], user_id, str(given.get("task") or ""))
        except GlyphhError as err:
            raise ValueError(f"{found[0].name} could not start: {err.message}") from err
        return heard(found[0].name, await settled(svc, bot.org_id, made.id))

    said = "Hand a task to one of the bots and get its answer back. It works under its own permissions."
    own = [
        Tool("list_bots", "list_bots", "Looked at the bots", "The org's bots: each one's name and what it is for.",
             NO_ARGS, True, call=list_bots),
        Tool("ask_bot", "ask_bot", "Asked a bot", said, ASKS, True, call=ask_bot, seconds=WAIT_SECONDS + 30),
        *crew_tools(svc, bot, user_id),
    ]  # fmt: skip
    return {t.name: t for t in own}


async def carried(svc: Any, bot: Any, run_id: uuid.UUID, question: dict[str, Any], answer: Any, by: Any) -> str:
    """The person answered a bot the orchestrator had asked: the answer goes to that bot's run, and the orchestrator
    is told what the bot then said (or stops again, when the bot asks again: Ask). With no answer, the person
    answered where the bot's own run waited and that run is over: the orchestrator is told how it ended. An answer
    the bot's run does not take (it no longer waits, or it asks something else by now) changes nothing there: the
    orchestrator hears how that run stands, its question as it is now."""
    child, name = uuid.UUID(question["child_run"]), str(question.get("child_bot") or "The bot")
    if answer is not None:
        who = Principal(user_id=by, org_id=bot.org_id, role="member")
        with contextlib.suppress(GlyphhError):
            await svc.answer(who, child, answer)
    try:
        got = heard(name, await settled(svc, bot.org_id, child))
    except ValueError as err:
        return f"{str(err).rstrip('.')}. Tell the person."
    if got["status"] != "done":
        return f"{name} is still working on it. Tell the person it is taking longer."
    return f"{name} finished. Its answer:\n\n{got['answer']}\n\nTell the person, plainly."
