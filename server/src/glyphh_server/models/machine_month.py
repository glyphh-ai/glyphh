import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base


class MachineMonth(Base):
    """A hosted machine's month: what it cost at Fly's rates and what it charges with the org's markup, in
    micro-dollars, added each minute (its size's rate while started, its volume's always). Kept by the machine's id,
    its name and size copied, so a machine deleted mid-month is still billed for its days."""

    __tablename__ = "machine_months"

    rrotor_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(Text, primary_key=True)  # YYYY-MM
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    size: Mapped[str] = mapped_column(Text)
    cost_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    charge_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
