"""Ada versions (docs/specs/ada-cloud.md, 12): every version this service knows, newest first, with its status, its
release notes and how many of the org's models run it; and the latest stable, which a model gets when none is
named."""

from collections import Counter
from typing import Any

from fastapi import APIRouter, Request

from glyphh_ada import registry
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.call import call

router = APIRouter(tags=["ada"])


@router.get("/v1/ada", operation_id="listAdaVersions")
async def versions(who: AdaWho, request: Request) -> dict[str, Any]:
    """{latest_stable, contract, versions: [{name, kernel, status, beta, open, released, deprecated, ends,
    changes_answers, aliases, summary, notes, models}]}."""
    reg, day = registry.registry(), registry.today()
    models = await call(request, who, "", "models", {})
    running = Counter(getattr(reg.find(m["ada"]), "name", m["ada"]) for m in models)  # an alias counts as its version
    return {
        "latest_stable": reg.latest(day).name,
        "contract": registry.CONTRACT,
        "versions": [{**reg.view(v, day), "models": running[v.name]} for v in reg.versions],
    }
