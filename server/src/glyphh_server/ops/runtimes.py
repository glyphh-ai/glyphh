"""A person's runtimes. A local rrotor gets its runtime token from the install that starts it: one local runtime per
install, its token shown once and kept only as a hash; asking again rotates it. A new token starts the link's
sequence numbers again: the mod asks for one when it starts a rrotor whose /data holds none, a fresh volume."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

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
