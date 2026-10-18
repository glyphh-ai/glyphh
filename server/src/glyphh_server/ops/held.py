"""Hosted machines held past the plan: when an org lands on a plan that allows fewer machines than one of its people
holds (its subscription cancelled or ended, an Enterprise grant revoked or lapsed), every machine of each such person
is stopped and none of them starts (E_LIMIT, reason machines) until the org is on a plan that allows them. They keep
their disks, and may be deleted. The minute tick stops any that woke since (a request at its address wakes it on
Fly's proxy) and is the backstop for every path; a change the server makes itself holds them at once."""

import logging
import uuid

from sqlalchemy import Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, PlanVersion, Rrotor, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops import limits
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.plans import org_version
from glyphh_server.ops.runtimes import NOT_LINKED

log = logging.getLogger("glyphh.runtime")


async def check_start(conn: AsyncConnection, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Refused (E_LIMIT, reason machines) while the person holds more machines than the org's plan allows."""
    await limits.check_machines(conn, await limits.machines(conn, user_id), await org_version(conn, org_id), more=0)


def _past_the_plan():  # type: ignore[no-untyped-def]
    """The people holding more hosted machines than their org's plan allows."""
    held = (
        select(Rrotor.user_id, func.count().label("n"))
        .where(Rrotor.mode == "hosted")
        .group_by(Rrotor.user_id)
        .subquery()
    )
    return (
        select(held.c.user_id)
        .join(User, User.id == held.c.user_id)
        .join(Org, Org.id == User.org_id)
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .where(PlanVersion.max_machines.is_not(None), held.c.n > PlanVersion.max_machines)
    )


async def hold(conn: AsyncConnection, fly: Fly, org_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    """Every machine of the people past their plan (the org's, or every org's) that is not stopped, stopped: the
    machines stopped. A stop Fly refuses is logged and tried again at the next tick."""
    people = _past_the_plan()
    if org_id is not None:
        people = people.where(Org.id == org_id)
    found = select(Rrotor.id, Rrotor.fly_machine_id).where(
        Rrotor.mode == "hosted", Rrotor.user_id.in_(people), Rrotor.state != NOT_LINKED
    )
    stopped: list[uuid.UUID] = []
    for row in list(await conn.execute(found)):
        if await _stop(fly, row):
            stopped.append(row.id)
    if stopped:
        await conn.execute(update(Rrotor).where(Rrotor.id.in_(stopped)).values(state=NOT_LINKED))
    return stopped


async def _stop(fly: Fly, row: Row) -> bool:
    try:
        await fly.stop(str(row.fly_machine_id))
    except Exception:
        log.exception("machine past the plan not stopped", extra=fields(runtime=str(row.id)))
        return False
    log.info("machine past the plan stopped", extra=fields(runtime=str(row.id)))
    return True
