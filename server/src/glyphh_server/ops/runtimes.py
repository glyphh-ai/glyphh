"""A person's runtimes.

A local rrotor gets its runtime token from the install that starts it: one local runtime per install, its token
shown once and kept only as a hash; asking again rotates it. A new token starts the link's sequence numbers again:
the mod asks for one when it starts a rrotor whose /data holds none, a fresh volume.

A hosted rrotor is a Fly machine and its volume, as many per person as the plan's machines (ops/machines.py makes,
starts, stops, restarts and deletes them); here is how the person's first one is shown to the routes made for one,
and which runtime a call or a deploy goes to."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

NOT_LINKED: str = "stopped"
FIRST = (Rrotor.created_at, Rrotor.id)  # a person's machines in the order they were made: the first is the oldest


class LocalRuntime(BaseModel):
    runtime_id: uuid.UUID
    token: str = Field(description="The runtime's token for its outbound link: shown once, never stored")


class HostedRuntime(BaseModel):
    runtime_id: uuid.UUID | None = Field(description="None until the runtime is first started")
    address: str | None = Field(description="Where it is called: https://<machine>.<domain>, REST and /mcp")
    state: str = Field(description="none, stopped, online or offline")
    region: str | None
    image_version: str | None
    last_seen_at: datetime | None
    seconds_used: int = Field(description="Online time this calendar month")


async def issue_local(conn: AsyncConnection, who: Principal) -> LocalRuntime:
    if who.install_id is None:
        raise Invalid("A local runtime belongs to an install: link it from Claude Code.", reason="no_install")
    token = make_secret()
    made = upsert(Rrotor).values(
        user_id=who.user_id, mode="local", install_id=who.install_id, state=NOT_LINKED, token_hash=hash_secret(token)
    )
    rotated = made.on_conflict_do_update(
        index_elements=[Rrotor.install_id], set_={"token_hash": made.excluded.token_hash, "seq": 0}
    ).returning(Rrotor.id)
    runtime_id = (await conn.execute(rotated)).scalar_one()
    return LocalRuntime(runtime_id=runtime_id, token=token)


async def runtime_for(conn: AsyncConnection, who: Principal, runtime_id: uuid.UUID | None) -> uuid.UUID:
    """The runtime a deploy goes to: the one named, when it is the person's; else the local one of the install
    calling; else the person's first hosted machine."""
    mine = select(Rrotor.id).where(Rrotor.user_id == who.user_id)
    if runtime_id is not None:
        found = (await conn.execute(mine.where(Rrotor.id == runtime_id))).scalar()
        if found is None:
            raise NotFound("You have no such runtime.", runtime_id=str(runtime_id))
        return found
    local = mine.where(Rrotor.install_id == who.install_id) if who.install_id else mine.where(False)
    hosted = mine.where(Rrotor.mode == "hosted").order_by(*FIRST).limit(1)
    found = (await conn.execute(local)).scalar() or (await conn.execute(hosted)).scalar()
    if found is None:
        raise NotFound("You have no runtime. Start one from Claude.", reason="no_runtime")
    return found


# Hosted


def month_of(now: datetime) -> str:
    return now.strftime("%Y-%m")


async def hosted_view(conn: AsyncConnection, who: Principal, domain: str) -> HostedRuntime:
    """The person's first hosted machine, as the routes made for one runtime show it."""
    mine = select(Rrotor).where(Rrotor.user_id == who.user_id, Rrotor.mode == "hosted").order_by(*FIRST).limit(1)
    row = (await conn.execute(mine)).first()
    if row is None:
        return HostedRuntime(
            runtime_id=None,
            address=None,
            state="none",
            region=None,
            image_version=None,
            last_seen_at=None,
            seconds_used=0,
        )
    this_month = row.month == month_of(datetime.now(UTC))
    return HostedRuntime(
        runtime_id=row.id,
        address=f"https://{row.fly_machine_id}.{domain}" if row.fly_machine_id else None,
        state=row.state,
        region=row.region,
        image_version=row.image_version,
        last_seen_at=row.last_seen_at,
        seconds_used=row.month_seconds if this_month else 0,
    )
