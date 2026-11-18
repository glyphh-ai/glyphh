import uuid
from typing import Literal

from pydantic import BaseModel


class Principal(BaseModel):
    """Who is calling: the grant behind the access token, its user, and the one org they are in."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: Literal["admin", "member"]
    grant_id: uuid.UUID
    client_id: uuid.UUID  # the OAuth client the grant is for: the platform's own
    suspended: bool = False  # the org is suspended by Glyphh's staff: refused (api/auth.py)
    email: str = ""  # their verified sign-in email
