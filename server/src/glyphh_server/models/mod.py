from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base


class Mod(Base):
    """A mod Glyphh ships for Claude. A plan version includes the mods its mod_limits names; a retired mod is in no
    license. Retired with active=false, never deleted."""

    __tablename__ = "mods"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")
