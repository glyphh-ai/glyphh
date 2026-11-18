"""The staff view's landing dashboard, its infrastructure page and the alerts alone."""

from typing import Annotated

from fastapi import APIRouter, Query

from glyphh_server.admin import health
from glyphh_server.admin.alerts import Alert
from glyphh_server.admin.dashboard import Dashboard, dashboard
from glyphh_server.admin.health import Infra
from glyphh_server.api.admin.deps import Staff

router = APIRouter()

Days = Annotated[int, Query(ge=1, le=366, description="How many days back, today included (UTC)")]


@router.get("/dashboard", operation_id="adminDashboard")
async def get_dashboard(staff: Staff, days: Days = 30) -> Dashboard:
    """Totals and each day's sign-ups and paid conversions; revenue and the plan mix from the database (never
    Stripe)."""
    return await dashboard(staff.conn, days)


@router.get("/infra", operation_id="adminInfra")
async def get_infra(staff: Staff) -> Infra:
    """Latency, requests and errors by route, Postgres, Redis, the tick, and the alerts."""
    return await health.health(staff.conn, staff.request.app.state.redis)


@router.get("/alerts", operation_id="adminAlerts")
async def get_alerts(staff: Staff) -> list[Alert]:
    """What needs a person now: the thresholds against the server's own measures and its open errors."""
    return await health.current_alerts(staff.conn, staff.request.app.state.redis)
