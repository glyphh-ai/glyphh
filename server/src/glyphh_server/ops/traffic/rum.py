"""The account's Web Analytics (Cloudflare's RUM beacon, rumPageloadEventsAdaptiveGroups), when it is on and the token
may read the account: each day's page loads by hostname and page, and by hostname and referrer, the last week."""

from datetime import datetime
from typing import Any

from glyphh_server.ops.cloudflare import Cloudflare, CloudflareError
from glyphh_server.ops.traffic import queries as q
from glyphh_server.ops.traffic.queries import DAY, Limits
from glyphh_server.ops.traffic.store import Tops

WINDOWS: Limits = Limits(not_older=7 * DAY)
MOST_WINDOWS: int = 8
KINDS: tuple[tuple[str, str], ...] = (("requestPath", "rum_page"), ("refererHost", "rum_referrer"))


async def rum(cf: Cloudflare, account: str, now: datetime) -> tuple[Tops, dict[str, Any]]:
    """The account's page loads as tops keyed by hostname, or none and why."""
    tops: Tops = {}
    for day, start, end in q.windows(now, WINDOWS, MOST_WINDOWS):
        for dim, kind in KINDS:
            window = {"account": account, "start": q.stamp(start), "end": q.stamp(end)}
            try:
                data = await cf.query(q.RUM % {"dim": dim}, window)
            except CloudflareError as err:
                return {}, q.note(err)
            for row in q.groups(data, "accounts", "rumPageloadEventsAdaptiveGroups"):
                dims = row.get("dimensions") or {}
                if key := dims.get(dim):
                    at = (dims.get("requestHost") or "", day, kind, key)
                    tops[at] = tops.get(at, 0) + int(row.get("count") or 0)
    return tops, {"ok": True, "days": WINDOWS.days}
