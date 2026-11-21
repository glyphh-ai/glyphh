from fastapi import APIRouter

from glyphh_server.api.auth import Cfg, Conn
from glyphh_server.ops import plans
from glyphh_server.ops.plans import PlanView

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/plans", operation_id="listPlans")
async def list_plans(conn: Conn, settings: Cfg) -> list[PlanView]:
    """Each plan's newest version: its price, its limits (runtime nodes, precedents), its features and which features
    are built, and with Ada Cloud on its cloud limits (precedents and reads a month, calls a second, whether reads past
    the month are metered)."""
    return await plans.list_plans(conn, settings.ada_cloud)
