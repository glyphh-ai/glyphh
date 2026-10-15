from fastapi import APIRouter

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import addons
from glyphh_server.ops.addons import AddonView

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/addons", operation_id="listAddons")
async def list_addons(caller: Caller, conn: Conn) -> list[AddonView]:
    """The add-ons for the org's plan: each on sale and each the org has, its price, whether the plan may have it, the
    mod's limits on the plan, and whether it is added."""
    return await addons.list_addons(conn, caller.org_id)
