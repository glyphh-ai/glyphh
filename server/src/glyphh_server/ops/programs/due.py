"""The programs whose schedule is due, run by the same minute tick as the bots' (ops/tend.py, ops/bots/due.py) and
in the same way: each due program (every org's) has its next run worked out again from now before its run starts,
so a missed tick fires it once; a run is started as its schedule's (`trigger: schedule`), logged and audited as any;
one that cannot start (its last run still live, its steps not ready) is skipped this time, and the skip logged."""

import logging
from datetime import datetime

from sqlalchemy import select, update

from glyphh_server.errors import GlyphhError
from glyphh_server.models import Program
from glyphh_server.ops.bots import schedule
from glyphh_server.ops.bots.schedule import Schedule
from glyphh_server.ops.programs.service import Programs

log = logging.getLogger("glyphh.programs")


async def fire(programs: Programs, at: datetime | None = None) -> int:
    """Every program due by `at` (now) started with its schedule's input: how many were."""
    at = at or schedule.now()
    async with programs.engine.begin() as conn:
        found = select(Program).where(Program.next_run_at <= at).with_for_update(skip_locked=True)
        due = (await conn.execute(found)).all()
        for program in due:
            then = schedule.next_after(Schedule(**program.schedule), at)
            await conn.execute(update(Program).where(Program.id == program.id).values(next_run_at=then))
    fired = 0
    for program in due:
        try:
            await programs.queued(program, program.created_by, Schedule(**program.schedule).input, "schedule")
            fired += 1
        except GlyphhError as err:
            log.info("scheduled run of program %s skipped: %s", program.id, err.message)
    return fired
