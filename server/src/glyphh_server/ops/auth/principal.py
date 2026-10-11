import uuid

from pydantic import BaseModel


class Principal(BaseModel):
    """Who is calling: every operation runs as one, and the org decides which rows it sees."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    oauth_client_id: uuid.UUID | None = None
    host_client_id: str | None = None
