"""What the org uses of its plan (docs/specs/ada-cloud.md, section 7): the precedents its models hold, against the
plan's cap (GLYPHH_ADA_PRECEDENT_CAPS by the plan's name; null, no cap). Requests are not counted until metering
(the plan's step 6): `requests` is null until then."""

from typing import Any

from fastapi import APIRouter, Request

from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.call import call

router = APIRouter(tags=["usage"])


@router.get("/v1/usage", operation_id="getAdaUsage")
async def get_usage(who: AdaWho, request: Request) -> dict[str, Any]:
    """The plan, the precedents held across the org's models against its cap, and the models."""
    models = await call(request, who, "", "models", {})
    used = sum(int(m["precedents"]) for m in models)
    return {
        "plan": who.plan,
        "models": len(models),
        "precedents": {"used": used, "max": who.cap},
        "requests": None,
    }
