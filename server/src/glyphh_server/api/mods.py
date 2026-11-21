from fastapi import APIRouter

from glyphh_server.api.auth import Conn
from glyphh_server.ops import mods
from glyphh_server.ops.mods import ModView

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/mods", operation_id="listMods")
async def list_mods(conn: Conn) -> list[ModView]:
    """The catalog: each mod's slug, name, description, and the plans that include it (every plan)."""
    return await mods.list_mods(conn)
