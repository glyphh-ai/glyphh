import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

ADDON_STATUSES: tuple[str, ...] = ("active", "removed")


class Addon(Base):
    """A mod sold as an add-on to the plan, at one moment: its Stripe price, per seat or flat, the paid plans it may be
    added to, whether a Free org may have it, and the mod's limits on each plan ({"<plan>" | "*": {"<limit>": number |
    null}}, "*" for every plan not named). Never changed: a new price is a new version. Off sale with active=false."""

    __tablename__ = "addons"
    __table_args__ = (
        UniqueConstraint("mod", "version", name="addons_version"),
        CheckConstraint("price_cents >= 0", name="addons_price"),
        CheckConstraint("jsonb_typeof(limits) = 'object'", name="addons_limits"),
    )

    id: Mapped[uuid.UUID] = guid()
    mod: Mapped[str] = mapped_column(ForeignKey("mods.slug", ondelete="RESTRICT"), index=True)
    version: Mapped[int]
    stripe_price_id: Mapped[str | None] = mapped_column(Text, unique=True)
    price_cents: Mapped[int]
    per_seat: Mapped[bool] = mapped_column(server_default="true")
    plans: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    free: Mapped[bool] = mapped_column(server_default="false")
    limits: Mapped[dict[str, dict[str, Any]]] = mapped_column(JSONB, server_default="{}")
    active: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = created_at()


class OrgAddon(Base):
    """An add-on an org has, kept true to its Stripe subscription: the version it sells, its subscription item and
    quantity; active while the item is on the subscription, removed after."""

    __tablename__ = "org_addons"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="org_addons_quantity"),
        CheckConstraint(f"status IN {ADDON_STATUSES}", name="org_addons_status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    mod: Mapped[str] = mapped_column(ForeignKey("mods.slug", ondelete="RESTRICT"), primary_key=True)
    addon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addons.id", ondelete="RESTRICT"), index=True)
    stripe_item_id: Mapped[str | None] = mapped_column(Text, unique=True)
    quantity: Mapped[int] = mapped_column(server_default="1")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
