"""What a runtime reports about itself, applied as its owner: the calls each runtime key let in, and the models it
deployed, whether or not the server asked for the deploy. Never a call's inputs or outputs, never a key."""

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Model, ModelVersion, RuntimeKey
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Deployed, Usage
from glyphh_server.ops.runtime_keys import held_by


async def apply_usage(conn: AsyncConnection, runtime: Runtime, message: Usage) -> None:
    """Each key's calls added to its count and its last use moved on; a key this runtime does not hold is passed
    over (deleted since, or never its)."""
    for use in message.keys:
        await conn.execute(
            update(RuntimeKey)
            .where(held_by(runtime.id), RuntimeKey.key_hash == use.key_sha256)
            .values(
                calls=RuntimeKey.calls + use.calls,
                last_used_at=func.greatest(func.coalesce(RuntimeKey.last_used_at, use.last_used_at), use.last_used_at),
            )
        )


async def _model_for(conn: AsyncConnection, runtime: Runtime, message: Deployed) -> uuid.UUID:
    """The owner's model of that name (the newest, should a name have been used twice), made when it is new."""
    found = select(Model.id).where(Model.user_id == runtime.user_id, Model.name == message.model)
    model_id = (await conn.execute(found.order_by(Model.created_at.desc()).limit(1))).scalar()
    if model_id is not None:
        return model_id
    made = insert(Model).values(user_id=runtime.user_id, org_id=runtime.org_id, name=message.model, repo=message.repo)
    return (await conn.execute(made.returning(Model.id))).scalar_one()


async def version_for(conn: AsyncConnection, runtime: Runtime, message: Deployed) -> tuple[uuid.UUID, uuid.UUID]:
    """The model and version a deploy names, the version by its commit (its identity); recorded when the server has
    not seen it, with the runtime's number, or the next free one should that number be another commit's."""
    model_id = await _model_for(conn, runtime, message)
    by_commit = select(ModelVersion.id).where(
        ModelVersion.model_id == model_id, ModelVersion.commit_sha == message.commit_sha
    )
    found = (await conn.execute(by_commit)).scalar()
    if found is not None:
        return model_id, found
    taken = select(func.max(ModelVersion.version)).where(ModelVersion.model_id == model_id)
    highest = (await conn.execute(taken)).scalar() or 0
    number = message.version if message.version > highest else highest + 1
    made = insert(ModelVersion).values(
        model_id=model_id, version=number, commit_sha=message.commit_sha, manifest=message.manifest or {}
    )
    return model_id, (await conn.execute(made.returning(ModelVersion.id))).scalar_one()
