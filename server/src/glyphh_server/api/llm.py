"""The Glyphh-hosted models on the account API (docs/specs/tokens.md): the models and their rates (anyone may read
them, as the plans), and the org's tokens day by day. Their inference is at the Ada hosts (api/inference.py)."""

from typing import Annotated

from fastapi import APIRouter, Query

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.llm import registry, usage
from glyphh_server.llm.registry import Models
from glyphh_server.llm.usage import Days

router = APIRouter(prefix="/v1/llm", tags=["hosted models"])


@router.get("/models", operation_id="listHostedModels")
async def list_models() -> Models:
    """Each Glyphh-hosted model: its id (what a request sends as `model`), status, context, and its rates in US cents
    per million input and output tokens past the plan's allowance, and how much of the allowance a token uses."""
    return registry.listing()


@router.get("/usage", operation_id="hostedModelUsage")
async def get_usage(
    caller: Caller, conn: Conn, days: Annotated[int, Query(ge=1, le=90, description="Days back, today's included")] = 30
) -> Days:
    """The org's hosted-model tokens by UTC day and model, oldest first: input, output, requests, and what was charged
    past the allowance."""
    return await usage.days(conn, caller.org_id, days)
