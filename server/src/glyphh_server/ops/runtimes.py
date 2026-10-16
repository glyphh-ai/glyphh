"""A person's runtimes. A local rrotor gets its runtime token from the install that starts it: one local runtime per
install, its token shown once and kept only as a hash; asking again rotates it. A new token starts the link's
sequence numbers again: the mod asks for one when it starts a rrotor whose /data holds none, a fresh volume."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

NOT_LINKED: str = "stopped"


class LocalRuntime(BaseModel):
    runtime_id: uuid.UUID
    token: str = Field(description="The runtime's token for its outbound link: shown once, never stored")


async def issue_local(conn: AsyncConnection, who: Principal) -> LocalRuntime:
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
    """The runtime a deploy or a call goes to: the one named, when it is the person's; else the local one of the
    install calling, else the person's runtime seen most recently (the connector calls from no install)."""
    mine = select(Rrotor.id).where(Rrotor.user_id == who.user_id)
    if runtime_id is not None:
        found = (await conn.execute(mine.where(Rrotor.id == runtime_id))).scalar()
        if found is None:
            raise NotFound("You have no such runtime.", runtime_id=str(runtime_id))
        return found
    if who.install_id is not None:
        found = (await conn.execute(mine.where(Rrotor.install_id == who.install_id))).scalar()
        if found is not None:
            return found
    found = (await conn.execute(mine.order_by(Rrotor.last_seen_at.desc().nulls_last(), Rrotor.id).limit(1))).scalar()
    if found is None:
        raise NotFound("You have no runtime. Start one from Claude (/ada start).", reason="no_runtime")
    return found
