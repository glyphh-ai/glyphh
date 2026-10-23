"""A sign-up's source: the website's campaign tags, sent by the platform as a sign-in finishes (ops/attribution.py)."""

from fastapi import APIRouter

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import attribution
from glyphh_server.ops.attribution import Source, Stored

router = APIRouter(prefix="/v1", tags=["account"])


@router.post("/me/source", operation_id="setSignUpSource")
async def set_source(body: Source, caller: Caller, conn: Conn) -> Stored:
    """The tags of the link the person arrived at glyphh.ai on (the website's glyphh_src cookie), kept on their account
    and their new org, once, within a day of the account being made; else nothing changes."""
    return await attribution.store(conn, caller, body)
