import uuid
from typing import Literal

from pydantic import BaseModel


class Principal(BaseModel):
    """Who is calling: the install behind the token, its user, and the one org they are in."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: Literal["admin", "member"]
    install_id: uuid.UUID
