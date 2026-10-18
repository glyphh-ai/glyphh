from datetime import UTC, datetime

from fastapi import APIRouter, Request

from glyphh_server.api.auth import Conn
from glyphh_server.ops import plans
from glyphh_server.ops.plans import PlanView
from glyphh_server.ops.rates import Rates, public_rates

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/plans", operation_id="listPlans")
async def list_plans(conn: Conn) -> list[PlanView]:
    """Each plan's newest version: its price, its limits (hosted machines, managed precedents) and its features;
    never the markup on hosting."""
    return await plans.list_plans(conn)


@router.get("/rates", operation_id="listRates")
async def list_rates(conn: Conn, request: Request) -> Rates:
    """The hosted machines' rates in force: Fly's own, and what each self-serve paid plan is billed, a 30-day month and
    a second of each size and a GB-month of volume. Enterprise's are set in each contract."""
    region = request.app.state.settings.fly_region
    return await public_rates(conn, region, datetime.now(UTC).date())
