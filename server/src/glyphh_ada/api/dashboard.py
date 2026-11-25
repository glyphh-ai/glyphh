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
READS: tuple[str, ...] = ("decide", "query", "probabilities", "facts", "beam")


def _answers(window: list[date], counted: dict[date, dict[str, int]]) -> list[dict[str, Any]]:
    """Each output's decides in the window (the default's first, then the named ones by name): how many, how many
    asked a person, how sure (in tenths), and how many a day."""
    found: dict[str | None, dict[str, Any]] = {}
    for i, day in enumerate(window):
        for metric, n in counted.get(day, {}).items():
            kind, output = days.split(metric)
            if kind.startswith("read:"):
                continue
            if output not in found:
                each = [{"decided": 0, "asked": 0} for _ in window]
                found[output] = {"output": output, "decided": 0, "asked": 0, "sure": [0] * 10, "days": each}
            one = found[output]
            if kind == days.DECIDED:
                one["decided"] += n
                one["days"][i]["decided"] += n
            elif kind == days.ASKED:
                one["asked"] += n
                one["days"][i]["asked"] += n
            else:
                one["sure"][int(kind.removeprefix(days.SURE))] += n
    return sorted(found.values(), key=lambda a: (a["output"] is not None, a["output"] or ""))


@router.get("/stats", operation_id="getAdaModelStats")
async def stats(
    name: str, who: AdaWho, request: Request, last: int = Query(30, alias="days", ge=1, le=DAYS_MAX)
) -> dict[str, Any]:
    """The model's dashboard: its active version, precedents, outcomes and latest jobs (from the store), its
    precedents by the cases' days (`growth`), the org's precedents against the plan's, and its last `days` days (UTC,
    every one of them; those before it was made are empty): `days`, each day's reads by kind and decides answered
    (every output's together) and how many asked a person; `sure`, how many of the window's decides were how sure
    (the decided outcome's probability), in tenths from 0-0.1 to 0.9-1; `answers`, the same for each output apart
    (the default first, output null), with its decides a day. Counts are the database's and Redis's that the minute
    tick has not taken yet, so a read shows at once."""
    found = dict(await call(request, who, name, "stats", {}))
    today = datetime.now(UTC).date()
    start = today - timedelta(days=last - 1)
    born = datetime.fromisoformat(str(found["created_at"])).date()
    async with request.app.state.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        counted = await days.daily(conn, request.app.state.redis, who.org_id, name, max(start, born))
        plan = await allowance(conn, who.org_id)
        _, held = await usage.held(conn, who.org_id)
    window = [start + timedelta(days=i) for i in range(last)]
    answers = _answers(window, counted)
    every = [
        {
            "day": day.isoformat(),
            "reads": {op: counted.get(day, {}).get(f"read:{op}", 0) for op in READS},
            "decided": sum(a["days"][i]["decided"] for a in answers),
            "asked": sum(a["days"][i]["asked"] for a in answers),
        }
        for i, day in enumerate(window)
    ]
    sure = [sum(a["sure"][tenth] for a in answers) for tenth in range(10)]
    plan_held = {"plan": plan.plan, "precedents": {"used": held, "max": plan.precedents}}
    return {**found, "plan": plan_held, "days": every, "sure": sure, "answers": answers}


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
