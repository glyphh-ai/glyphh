"""The bots whose schedule is due, run by the minute tick (ops/tend.py, which holds its lock, so one process fires
them). Each due bot (every org's: no org is entered) has its next run worked out again from now before its run is
queued, so a tick missed (the server down for an hour) fires a bot once, not once per run it missed. A bot whose last
run is still live (queued, running or waiting on the person) is skipped this time, as is one that runs on a rrotor
(runs are not sent to rrotors yet) or one with no Anthropic key to run on; each skip is logged."""

import logging
from datetime import datetime

from sqlalchemy import select, update

from glyphh_server.errors import GlyphhError
from glyphh_server.models import Bot
from glyphh_server.ops.bots import schedule
from glyphh_server.ops.bots.schedule import Schedule
from glyphh_server.ops.bots.service import Bots

log = logging.getLogger("glyphh.bots")


async def fire(bots: Bots, at: datetime | None = None) -> int:
    """Every bot due by `at` (now) queued a run with its schedule's input: how many were."""
    at = at or schedule.now()
    async with bots.engine.begin() as conn:
        due = (await conn.execute(select(Bot).where(Bot.next_run_at <= at).with_for_update(skip_locked=True))).all()
        for bot in due:
            then = schedule.next_after(Schedule(**bot.schedule), at)
            await conn.execute(update(Bot).where(Bot.id == bot.id).values(next_run_at=then))
    fired = 0
    for bot in due:
        try:
            await bots.queued(bot, bot.created_by, Schedule(**bot.schedule).input)
            fired += 1
        except GlyphhError as err:
            log.info("scheduled run of bot %s skipped: %s", bot.id, err.message)
    return fired
