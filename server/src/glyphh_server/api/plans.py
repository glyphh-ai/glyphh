from datetime import UTC, datetime

from fastapi import APIRouter

from glyphh_server.api.auth import Cfg, Conn
from glyphh_server.ops import plans
from glyphh_server.ops.hosted import require_hosting
from glyphh_server.ops.plans import PlanView
from glyphh_server.ops.rates import Rates, public_rates

router = APIRouter(prefix="/v1", tags=["plans and billing"])


@router.get("/plans", operation_id="listPlans")
async def list_plans(conn: Conn, settings: Cfg) -> list[PlanView]:
    """Each plan's newest version: its price, its limits (hosted machines, 0 for every plan while hosting is off;
    managed precedents) and its features; never the markup on hosting."""
    return await plans.list_plans(conn, settings)


@router.get("/rates", operation_id="listRates")
async def list_rates(conn: Conn, settings: Cfg) -> Rates:
    """The hosted machines' rates in force: each size's machine, and what each self-serve paid plan is billed for it,
    all in, a 30-day month and a second of each size and a GB-month of volume. Never Fly's own rates or the markup.
    Enterprise's are set in each contract. With hosting off, E_UNAVAILABLE `hosting_off`."""
    require_hosting(settings)
    return await public_rates(conn, settings.fly_region, datetime.now(UTC).date())
