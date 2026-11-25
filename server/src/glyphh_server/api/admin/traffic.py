"""Glyphh's own sites' traffic, from Cloudflare's analytics as the hourly pull kept it, and its public repositories'
from GitHub's."""

from typing import Annotated

from fastapi import APIRouter, Query

from glyphh_server.admin.traffic import Traffic, traffic
from glyphh_server.api.admin.deps import Staff

router = APIRouter()


@router.get("/traffic", operation_id="adminTraffic")
async def get_traffic(
    staff: Staff, days: Annotated[int, Query(ge=1, le=366, description="How many days back, today included (UTC)")] = 30
) -> Traffic:
    """Each zone's and hostname's days, countries, pages and referrers, what its plan allowed and when it was pulled;
    the last 7 and 30 days' visitors and page views against the period before, with sign-ups. Not connected without
    GLYPHH_CLOUDFLARE_API_TOKEN. `github`: each public repository's views and clones (unique visitors and cloners),
    the last 14 days and since tracking began, by day, and its popular referrers and paths; not connected without
    GLYPHH_GITHUB_TRAFFIC_TOKEN."""
    settings = staff.request.app.state.settings
    connected = bool(settings.cloudflare_api_token)
    return await traffic(staff.conn, connected, days, github_connected=bool(settings.github_traffic_token))
