"""Hosted machines held past the plan. A plan's machines are the org's, all its people's together, its oldest first:
when an org lands on a plan that allows fewer than it holds (its subscription cancelled or ended, an Enterprise grant
revoked or lapsed), its newest machines beyond the plan's are stopped and none of them starts (E_LIMIT, reason
machines) until the org is on a plan that allows them; its oldest, up to the plan's, run as before. Held machines keep
their disks, and may be deleted (which lets the next oldest start). The minute tick stops any that woke since (a
request at its address wakes it on Fly's proxy) and is the backstop for every path; a change the server makes itself
holds them at once."""

import logging
import uuid

from sqlalchemy import Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, PlanVersion, Rrotor, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops import limits
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.plans import org_version
from glyphh_server.ops.runtimes import FIRST, NOT_LINKED

log = logging.getLogger("glyphh.runtime")


def _ranked():  # type: ignore[no-untyped-def]
    """Every hosted machine with its org, its org's plan's machines and its place among the org's, oldest first."""
    place = func.row_number().over(partition_by=User.org_id, order_by=FIRST).label("place")
    return (
        select(Rrotor.id, Rrotor.fly_machine_id, Rrotor.state, User.org_id, PlanVersion.max_machines, place)
        .join(User, User.id == Rrotor.user_id)
        .join(Org, Org.id == User.org_id)
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .where(Rrotor.mode == "hosted")
        .subquery()
    )


async def check_start(conn: AsyncConnection, runtime_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Refused (E_LIMIT, reason machines) for a machine past the plan's: one of the org's newest beyond it."""
    ranked = _ranked()
    row = (await conn.execute(select(ranked.c.place, ranked.c.max_machines).where(ranked.c.id == runtime_id))).one()
    if row.max_machines is not None and row.place > row.max_machines:
        used = await limits.org_machines(conn, org_id)
        await limits.check_machines(conn, used, await org_version(conn, org_id), more=0)


async def hold(conn: AsyncConnection, fly: Fly, org_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    """Every machine past its org's plan (the org's, or every org's) that is not stopped, stopped: the machines
    stopped. A stop Fly refuses is logged and tried again at the next tick."""
    ranked = _ranked()
    found = select(ranked.c.id, ranked.c.fly_machine_id).where(
        ranked.c.max_machines.is_not(None), ranked.c.place > ranked.c.max_machines, ranked.c.state != NOT_LINKED
    )
    if org_id is not None:
        found = found.where(ranked.c.org_id == org_id)
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
