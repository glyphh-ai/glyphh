"""The org's runtime nodes, as the server sees them: each node that heartbeats or links says its `node_id` (the
operator's own name for it), `cluster_id` and `role` (rrotor's docs/specs/cluster.md), kept per runtime with its
store's precedents and its version. A hosted or self-hosted runtime that has said no node is one node: a hosted one
always, a self-hosted one while seen (linked, or heard within NODE_WINDOW). A node not heard within it is not counted.

The count is soft: shown against the plan's runtime nodes ("4 nodes on a 3-node plan"), never refusing anything.
rrotor enforces the key's max_nodes itself, per cluster, at join."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from sqlalchemy import Row, func, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Node, Rrotor, User
from glyphh_server.ops.plans import org_version

NODE_WINDOW: timedelta = timedelta(hours=48)  # two daily heartbeats

NodeId = Annotated[str, Field(min_length=1, max_length=253, pattern=r"^\S+$", description="The node's own name")]
Role = Literal["standalone", "head", "follower"]


class NodeView(BaseModel):
    runtime_id: uuid.UUID
    runtime: str | None = Field(description="The runtime's name")
    mode: str = Field(description="hosted or self")
    node_id: str | None = Field(description="As the node said it; null: a runtime that has said no node")
    cluster_id: uuid.UUID | None
    role: Role | None
    precedents: int | None = Field(description="Its store's precedents, across its models, as it last said")
    version: str | None
    seen_at: datetime | None = Field(description="When it last heartbeat or linked")


class Nodes(BaseModel):
    count: int = Field(description="The org's runtime nodes now")
    max_nodes: int | None = Field(description="The plan's runtime nodes; null = unlimited")
    over: bool = Field(description="More nodes than the plan's: shown, never refused")
    nodes: list[NodeView]


async def record(conn: AsyncConnection, runtime_id: uuid.UUID, node_id: str, said: dict[str, object]) -> None:
    """A node as it said itself now (`cluster_id`, `role`, `precedents`, `version`), kept by its runtime and name."""
    values = {"cluster_id": None, "role": None, "precedents": None, "version": None} | said
    made = upsert(Node).values(rrotor_id=runtime_id, node_id=node_id, **values, seen_at=func.now())
    await conn.execute(
        made.on_conflict_do_update(
            index_elements=[Node.rrotor_id, Node.node_id], set_={**values, "seen_at": func.now()}
        )
    )


def _heard(row: Row) -> datetime | None:
    return max((t for t in (row.last_seen_at, row.last_heartbeat_at) if t is not None), default=None)


def _counts(row: Row, cutoff: datetime) -> bool:
    """A runtime that has said no node is one: a hosted one always, a self-hosted one while linked or heard since the
    cutoff."""
    heard = _heard(row)
    return row.mode == "hosted" or row.state == "online" or (heard is not None and heard > cutoff)


async def nodes(conn: AsyncConnection, org_id: uuid.UUID) -> Nodes:
    cutoff = datetime.now(UTC) - NODE_WINDOW
    people = select(User.id).where(User.org_id == org_id)
    runtimes = select(Rrotor.id, Rrotor.name, Rrotor.mode, Rrotor.state, Rrotor.image_version, Rrotor.precedents)
    runtimes = runtimes.add_columns(Rrotor.last_seen_at, Rrotor.last_heartbeat_at).where(
        Rrotor.user_id.in_(people), Rrotor.mode.in_(("hosted", "self"))
    )
    found = list(await conn.execute(runtimes.order_by(Rrotor.name, Rrotor.id)))
    said = select(Node).where(Node.rrotor_id.in_([r.id for r in found]), Node.seen_at > cutoff)
    by_runtime: dict[uuid.UUID, list[Row]] = {}
    for node in await conn.execute(said.order_by(Node.node_id)):
        by_runtime.setdefault(node.rrotor_id, []).append(node)
    views: list[NodeView] = []
    for r in found:
        own = {"runtime_id": r.id, "runtime": r.name, "mode": r.mode}
        for n in by_runtime.get(r.id, []):
            at = {"node_id": n.node_id, "cluster_id": n.cluster_id, "role": n.role, "seen_at": n.seen_at}
            views.append(NodeView(**own, **at, precedents=n.precedents, version=n.version))
        if r.id not in by_runtime and _counts(r, cutoff):
            none = {"node_id": None, "cluster_id": None, "role": None, "seen_at": _heard(r)}
            views.append(NodeView(**own, **none, precedents=r.precedents, version=r.image_version))
    allowed = (await org_version(conn, org_id)).max_machines
    return Nodes(count=len(views), max_nodes=allowed, over=allowed is not None and len(views) > allowed, nodes=views)
