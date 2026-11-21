"""API keys for Ada Cloud, made by a signed-in person (not by a key): list, make (shown once), revoke, and delete
once revoked or expired."""

import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from glyphh_ada import keys
from glyphh_ada.api.body import bounded
from glyphh_ada.keys import CloudKey, MadeCloudKey
from glyphh_server.api.auth import Caller, Conn

router = APIRouter(prefix="/v1/keys", tags=["keys"], dependencies=[Depends(bounded)])


class NewKey(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What the key is for")
    expires_in_days: int | None = Field(None, description="Days until the key expires, 1 to 365; left out, never")
    clearance: float = Field(1.0, ge=0, le=1, description="What of a model's secured roles the key may read")


@router.get("", operation_id="listApiKeys")
async def list_keys(caller: Caller, conn: Conn) -> list[CloudKey]:
    """Your API keys, live and revoked; never the keys themselves."""
    return await keys.listing(conn, caller)


@router.post("", operation_id="createApiKey", status_code=201)
async def create_key(body: NewKey, caller: Caller, conn: Conn) -> MadeCloudKey:
    """A new key, shown once: `Authorization: Bearer glyphh_ak_…` on every Ada call, in your org."""
    return await keys.create(conn, caller, body.name.strip(), body.expires_in_days, body.clearance)


@router.delete("/{key_id}", operation_id="revokeApiKey")
async def revoke_key(key_id: uuid.UUID, caller: Caller, conn: Conn) -> CloudKey:
    """Revoke one key."""
    return await keys.revoke(conn, caller, key_id)


@router.delete("/{key_id}/forever", operation_id="deleteApiKey", status_code=204)
async def delete_key(key_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Delete a revoked or expired key for good; a live one is refused (409): revoke it first."""
    await keys.delete(conn, caller, key_id)
    return Response(status_code=204)
