"""`GET /v1/usage`: what the caller's org uses of Ada Cloud against its plan (docs/specs/ada-cloud.md, 4.2 and 7):
{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}."""

from fastapi import APIRouter, Request

from glyphh_ada.api.auth import AdaWho
from glyphh_ada.usage import CloudUsage, cloud_usage
from glyphh_server.db import tenancy

router = APIRouter(tags=["usage"])


@router.get("/v1/usage", operation_id="getAdaUsage")
async def get_usage(who: AdaWho, request: Request) -> CloudUsage:
    """The plan, the org's models, the precedents they hold and the reads this month, against the plan's (reads past
    the month: metered on Pro and Team, refused on Free until it turns)."""
    state = request.app.state
    async with state.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await cloud_usage(conn, state.redis, who.org_id)
