import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base


class Deployment(Base):
    """A model version deployed to a hosted runtime; the active one is what a call runs."""

    __tablename__ = "deployments"

    rrotor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), primary_key=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active: Mapped[bool] = mapped_column(server_default="true")
