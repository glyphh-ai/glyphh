"""A program's `code` step (docs/specs/programs.md, 3): its function of `program.py` run in the sandbox of the rrotor
the program runs on, by that rrotor's own programs runtime (glyphh_bot's `code`, rrotor 0.10.0), with the folders
its bot was given there. The step is `dispatched` until the result comes back over the link (`landed`), which puts
the function's return value on the run and walks on. On Glyphh cloud a code step does not run (the open item of the
spec's section 7): such a program is a rrotor's."""

import json
import re
from typing import Any

from sqlalchemy import update

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import ProgramRun
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.programs import flow, runs
from glyphh_server.ops.programs.steps import Went

PROGRAM: str = "glyphh_bot"
FUNCTION: str = "code"
RROTOR_MIN: tuple[int, int] = (0, 10)
PLACE: str = "The program's rrotor"
OLD: str = "{name} runs rrotor {version}, which cannot run a program's code: update it to rrotor 0.10.0 or later."
RESULT_MAX: int = 1_000_000


def runs_code(version: str | None) -> bool:
    found = re.match(r"(\d+)\.(\d+)", version or "")
    return found is not None and (int(found[1]), int(found[2])) >= RROTOR_MIN


async def send(svc: Any, program: Any, run: Any, step: dict[str, Any], bot: Any, outputs: dict[str, Any]) -> Went:
    """The function sent to the program's rrotor; the run waits for it, dispatched."""
    given = flow.render(step.get("input") or {}, outputs)
    sent = {"source": program.source, "function": step["function"], "given": given}
    try:
        async with svc.engine.begin() as conn:
            await tenancy.enter(conn, program.org_id)
            place = await calls.linked(conn, program.runs_on)
        calls.fits(sent, "The program's code and its input")
    except GlyphhError as err:
        return Went(error=err.message)
    if not runs_code(place.version):
        return Went(error=OLD.format(name=place.name, version=place.version or "an earlier version"))
    folders = bot.folders if bot is not None else []
    # dispatched before it is sent: its result may land at once
    await runs.put(svc.engine, program.org_id, run.id, when="running", status="dispatched")
    if not await calls.call(svc.remote.hub, program.runs_on, run.id, PROGRAM, FUNCTION, sent, folders):
        return Went(error=calls.offline(PLACE))
    return Went(dispatched=True, detail=f"Sent to {place.name}")


async def taken(engine: Any, runtime: Runtime, msg: Ran) -> Any:
    """The dispatched program run this result is for, taken once (None: not a program run's, or not new)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        took = (
            update(ProgramRun)
            .where(ProgramRun.id == msg.run_id, ProgramRun.status == "dispatched")
            .values(status="running")
            .returning(ProgramRun)
        )
        return (await conn.execute(took)).first()


def came(result: dict[str, Any]) -> Went:
    """What the rrotor's run of the function came to."""
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if result.get("status") != "done":
        return Went(error=str(data.get("reason") or data.get("message") or "The code failed on the rrotor."))
    got = data.get("result")
    if len(json.dumps(got, default=str)) > RESULT_MAX:
        return Went(error="The code's result was too large to keep.")
    return Went(result=got, detail="Ran on the rrotor")
