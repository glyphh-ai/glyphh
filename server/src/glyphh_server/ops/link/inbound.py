"""What a rrotor's hello and usage change, each in one transaction as the runtime's org. A usage report is applied
once: its `seq` must be past the runtime's last applied one, else it is a replay, acked and skipped."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Rrotor
from glyphh_server.ops import nodes
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Hello


async def first_time(conn: AsyncConnection, runtime: Runtime, seq: int) -> bool:
    """Whether this sequence number is new for this runtime; taking it is part of applying the message."""
    took = update(Rrotor).where(Rrotor.id == runtime.id, Rrotor.seq < seq).values(seq=seq).returning(Rrotor.id)
    return (await conn.execute(took)).first() is not None


async def record_hello(engine: AsyncEngine, runtime: Runtime, hello: Hello) -> None:
    """The node a hello says it is, when it says (ops/nodes.py), in one transaction as the owner."""
    if hello.node_id is None:
        return
    async with engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        said = {"cluster_id": hello.cluster_id, "role": hello.role, "version": hello.version}
        await nodes.record(conn, runtime.id, hello.node_id, said)
