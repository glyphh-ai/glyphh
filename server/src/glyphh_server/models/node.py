import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base

ROLES_IN_CLUSTER: tuple[str, ...] = ("standalone", "head", "follower")


class Node(Base):
    """One node of a runtime, as it said in its heartbeat or its link's hello (rrotor's docs/specs/cluster.md):
    `node_id` is the operator's own name for it (a pod name), unique within the runtime; its cluster, its role, its
    store's precedents and its version, as last said, and when. Counted against the plan's runtime nodes, softly:
    shown, never refused (ops/nodes.py)."""

    __tablename__ = "nodes"
    __table_args__ = (CheckConstraint(f"role IN {ROLES_IN_CLUSTER}", name="nodes_role"),)

    rrotor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), primary_key=True)
    node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    cluster_id: Mapped[uuid.UUID | None]
    role: Mapped[str | None] = mapped_column(Text)
    precedents: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[str | None] = mapped_column(Text)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
