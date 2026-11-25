import uuid
from typing import Literal

from pydantic import BaseModel


class Principal(BaseModel):
    """Who is calling: the install behind the token (the API) or the connector grant behind the access token (/mcp),
    its user, and the one org they are in."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: Literal["admin", "member"]
    install_id: uuid.UUID | None = None
    grant_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None  # the OAuth client the grant is for (the platform's own, or a connector's)
    suspended: bool = False  # the org is suspended by Glyphh's staff: refused (api/auth.py)
    email: str = ""  # their verified sign-in email
