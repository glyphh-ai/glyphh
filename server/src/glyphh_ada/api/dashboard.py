"""What the platform shows of one model beside its spec: its dashboard (GET …/stats: its usage and health, from the
store and from its days counted as they happen, days.py), its 3D view (GET …/map: a sample of its precedents with
their glyphs and nearest, glyphmap.py) and one precedent by its id (GET …/precedents/{id}, seen.py). Looks, not
reads: none is counted against the month."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

from glyphh_ada import days, usage
from glyphh_ada.allowance import allowance
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.call import call
from glyphh_ada.glyphmap import MAP_MAX
from glyphh_server.db import tenancy

router = APIRouter(prefix="/v1/models/{name}", tags=["dashboard"])
DAYS_MAX: int = 90
READS: tuple[str, ...] = ("decide", "query", "probabilities", "facts")


def _day(day: date, counted: dict[str, int]) -> dict[str, Any]:
    return {
        "day": day.isoformat(),
        "reads": {op: counted.get(f"read:{op}", 0) for op in READS},
        "decided": counted.get(days.DECIDED, 0),
        "asked": counted.get(days.ASKED, 0),
    }


@router.get("/stats", operation_id="getAdaModelStats")
async def stats(
    name: str, who: AdaWho, request: Request, last: int = Query(30, alias="days", ge=1, le=DAYS_MAX)
) -> dict[str, Any]:
    """The model's dashboard: its active version, precedents, outcomes and latest jobs (from the store), its
    precedents by the cases' days (`growth`), the org's precedents against the plan's, and its last `days` days (UTC,
    from when it was made): reads by kind, decides answered and how many asked a person; `sure`, how many of those
    decides were how sure (the decided outcome's probability), in tenths from 0-0.1 to 0.9-1."""
    found = dict(await call(request, who, name, "stats", {}))
    today = datetime.now(UTC).date()
    since = max(today - timedelta(days=last - 1), datetime.fromisoformat(str(found["created_at"])).date())
    async with request.app.state.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        counted = await days.daily(conn, who.org_id, name, since)
        plan = await allowance(conn, who.org_id)
        _, held = await usage.held(conn, who.org_id)
    window = [since + timedelta(days=i) for i in range((today - since).days + 1)]
    sure = [sum(c.get(f"{days.SURE}{tenth}", 0) for c in counted.values()) for tenth in range(10)]
    plan_held = {"plan": plan.plan, "precedents": {"used": held, "max": plan.precedents}}
    return {**found, "plan": plan_held, "days": [_day(d, counted.get(d, {})) for d in window], "sure": sure}


@router.get("/map", operation_id="getAdaModelMap")
async def glyph_map(
    name: str,
    who: AdaWho,
    request: Request,
    limit: int = Query(MAP_MAX, ge=1, le=MAP_MAX),
    layer: str | None = Query(None, max_length=200, description="One layer's glyphs; left out, the whole case's"),
) -> dict[str, Any]:
    """A sample of the model's precedents (up to 2,000) for its 3D view: each one's id, outcomes and glyph as bits
    (base64), and each one's nearest in the sample by the Jaccard similarity of their bits ([i, j, sim])."""
    args: dict[str, Any] = {"limit": limit} if layer is None else {"limit": limit, "layer": layer}
    return dict(await call(request, who, name, "map", args))


@router.get("/precedents/{precedent_id}", operation_id="getAdaPrecedent")
async def precedent(name: str, precedent_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """One precedent: its case (in the kernel's terms, cut to what the caller's clearance may see), its outcome
    (null when ungraded) and each named output's, who recorded it and when."""
    return dict(await call(request, who, name, "precedent", {"id": precedent_id}))
