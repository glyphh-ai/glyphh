"""A person's hosted machines: as many as their plan's machines, each named, of one size (small, medium or large),
made and started, stopped, restarted and deleted, each only by its owner. Deleting one destroys its machine and its
volume: nothing is kept past Fly's daily snapshots (5 days). The routes made for one runtime act on the first."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import Row, delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Rrotor
from glyphh_server.models.rrotor import SizeName
from glyphh_server.ops import limits
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.hosted import provision
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.plans import org_version
from glyphh_server.ops.runtimes import FIRST, NOT_LINKED, month_of

DEFAULT_NAME: str = "default"  # the machine the routes made for one runtime make
DEFAULT_SIZE: SizeName = "small"


class Machine(BaseModel):
    id: uuid.UUID
    name: str
    size: SizeName
    state: str = Field(description="stopped, online or offline")
    address: str | None = Field(description="Where it is called: https://<machine>.<domain>, REST and /mcp")
    month_seconds: int = Field(description="Its online time this calendar month")
    paused: bool = Field(description="The month's hours are spent: calls answer 402 until the month turns")
    created_at: datetime


_MINE = select(Rrotor).where(Rrotor.mode == "hosted")


def _view(row: Row, domain: str) -> Machine:
    this_month = row.month == month_of(datetime.now(UTC))
    return Machine(
        id=row.id,
        name=row.name,
        size=row.size,
        state=row.state,
        address=f"https://{row.fly_machine_id}.{domain}" if row.fly_machine_id else None,
        month_seconds=row.month_seconds if this_month else 0,
        paused=row.paused_at is not None and this_month,
        created_at=row.created_at,
    )


async def _row(conn: AsyncConnection, who: Principal, runtime_id: uuid.UUID) -> Row:
    row = (await conn.execute(_MINE.where(Rrotor.id == runtime_id, Rrotor.user_id == who.user_id))).first()
    if row is None:
        raise NotFound("You have no such hosted machine.", runtime_id=str(runtime_id))
    return row


async def list_machines(conn: AsyncConnection, who: Principal, domain: str) -> list[Machine]:
    rows = await conn.execute(_MINE.where(Rrotor.user_id == who.user_id).order_by(*FIRST))
    return [_view(r, domain) for r in rows]


async def machine(conn: AsyncConnection, who: Principal, runtime_id: uuid.UUID, domain: str) -> Machine:
    return _view(await _row(conn, who, runtime_id), domain)


async def create(conn: AsyncConnection, fly: Fly, who: Principal, name: str, size: SizeName) -> Machine:
    """A new machine, made and started (the app's doorman with the first one); past the plan's machines, or
    with a name the person has given another, refused."""
    await limits.lock_user(conn, who.user_id)
    await limits.check(conn, "machines", await limits.machines(conn, who.user_id), await org_version(conn, who.org_id))
    taken = _MINE.where(Rrotor.user_id == who.user_id, Rrotor.name == name)
    if (await conn.execute(taken)).first() is not None:
        raise Conflict("You have a machine of that name already.", reason="name", name=name)
    runtime_id = await provision(conn, fly, who, name, size)
    row = await _row(conn, who, runtime_id)
    await fly.start(str(row.fly_machine_id))
    return _view(row, fly.settings.fly_public_domain)


async def start(conn: AsyncConnection, fly: Fly, who: Principal, runtime_id: uuid.UUID) -> Machine:
    """Its machine started, unless it is online already. It is `stopped` until its rrotor links."""
    row = await _row(conn, who, runtime_id)
    if row.state != ONLINE:
        await fly.start(str(row.fly_machine_id))
    return _view(row, fly.settings.fly_public_domain)


async def _stopped(conn: AsyncConnection, fly: Fly, who: Principal, runtime_id: uuid.UUID) -> Machine:
    await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(state=NOT_LINKED))
    return await machine(conn, who, runtime_id, fly.settings.fly_public_domain)


async def stop(conn: AsyncConnection, fly: Fly, who: Principal, runtime_id: uuid.UUID) -> Machine:
    """Its machine stopped; a run in progress is left to the rrotor (it recovers it when next started)."""
    await fly.stop(str((await _row(conn, who, runtime_id)).fly_machine_id))
    return await _stopped(conn, fly, who, runtime_id)


async def restart(conn: AsyncConnection, fly: Fly, who: Principal, runtime_id: uuid.UUID) -> Machine:
    """Its machine restarted: its link drops and it links again, `stopped` until then."""
    await fly.restart(str((await _row(conn, who, runtime_id)).fly_machine_id))
    return await _stopped(conn, fly, who, runtime_id)


async def destroy(
    conn: AsyncConnection, fly: Fly, who: Principal, runtime_id: uuid.UUID, confirm: str | None = None
) -> None:
    """The machine, its volume and everything on it go, and the runtime row with them. Not undone. With `confirm`,
    refused unless it is the machine's name."""
    row = await _row(conn, who, runtime_id)
    if confirm is not None and confirm != row.name:
        raise Invalid(f"Type the machine's name, {row.name}, to delete it.", reason="confirm")
    await fly.destroy(str(row.fly_machine_id), row.fly_volume_id)
    await conn.execute(delete(Rrotor).where(Rrotor.id == runtime_id))


# The routes made for one runtime: the person's first machine.


async def first(conn: AsyncConnection, who: Principal) -> uuid.UUID:
    found = select(Rrotor.id).where(Rrotor.user_id == who.user_id, Rrotor.mode == "hosted").order_by(*FIRST)
    runtime_id = (await conn.execute(found.limit(1))).scalar()
    if runtime_id is None:
        raise NotFound("You have no hosted runtime yet.", reason="no_runtime")
    return runtime_id


async def start_first(conn: AsyncConnection, fly: Fly, who: Principal) -> None:
    """The first machine started; with none, one made (`default`, small)."""
    await limits.lock_user(conn, who.user_id)
    try:
        runtime_id = await first(conn, who)
    except NotFound:
        await create(conn, fly, who, DEFAULT_NAME, DEFAULT_SIZE)
        return
    await start(conn, fly, who, runtime_id)
