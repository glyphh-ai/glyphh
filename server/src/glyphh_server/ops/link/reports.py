"""What a runtime reports about itself, applied as its owner: the calls each runtime key let in, and its precedents
(the total across its Ada models). Never a call's inputs or outputs, never a key."""

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Rrotor, RuntimeKey
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Usage
from glyphh_server.ops.runtime_keys import held_by


async def apply_usage(conn: AsyncConnection, runtime: Runtime, message: Usage) -> None:
    """Each key's calls added to its count and its last use moved on; a key this runtime does not hold is passed
    over (deleted since, or never its). Its precedents, when said, are its total now."""
    if message.precedents is not None:
        values = {"precedents": message.precedents, "precedents_at": func.now()}
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime.id).values(values))
    for use in message.keys:
        await conn.execute(
            update(RuntimeKey)
            .where(held_by(runtime.id), RuntimeKey.key_hash == use.key_sha256)
            .values(
                calls=RuntimeKey.calls + use.calls,
                last_used_at=func.greatest(func.coalesce(RuntimeKey.last_used_at, use.last_used_at), use.last_used_at),
            )
        )
