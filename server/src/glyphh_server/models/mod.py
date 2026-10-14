from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base


class Mod(Base):
    """A mod Glyphh ships for Claude. A plan version includes every active mod (all_mods) or only the free ones; a mod
    once free stays free. Retired with active=false, never deleted."""

    __tablename__ = "mods"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    free: Mapped[bool]
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")
