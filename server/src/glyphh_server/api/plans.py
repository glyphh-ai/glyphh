from fastapi import APIRouter

from glyphh_server.api.auth import Conn
from glyphh_server.ops import plans
from glyphh_server.ops.plans import PlanView

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/plans", operation_id="listPlans")
async def list_plans(conn: Conn) -> list[PlanView]:
    """Each plan's newest version: its price, its limits (hosted machines, managed precedents) and its features;
    never the markup on hosting."""
    return await plans.list_plans(conn)
