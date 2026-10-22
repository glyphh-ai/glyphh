"""What the connector's Ada tools share (docs/specs/ada-cloud.md, 4.3): the person signed in as the Ada caller (their
org, full clearance as a sign-in has on the Ada API, their org's plan allowance), and one call to the workers through
the Ada app, exactly as the API makes it (glyphh_ada/api/call.py: the plan's checks, the message, the reply). The tools
exist only while Ada Cloud is on (registry.available), and run after the request's transaction has ended
(registry.DETACHED): they never touch ctx.conn."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import limits
from glyphh_ada.allowance import allowance
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.api.call import keyed, send
from glyphh_server.db import tenancy
from glyphh_server.mcp.tools.base import Context

NAME = Field(pattern=limits.NAME_PATTERN, description="The model's name (ada_models lists them)")
IDEMPOTENCY = Field(None, max_length=200, description="Sent again with the same key and cases, the write is made once")


class Named(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = NAME


async def caller(ctx: Context) -> AdaCaller:
    """The person signed in, acting in their org with full clearance and their org's plan allowance, read in a short
    transaction of its own: these tools run after the request's (registry.DETACHED)."""
    async with ctx.ada.engine.begin() as conn:
        await tenancy.enter(conn, ctx.who.org_id)
        allowed = await allowance(conn, ctx.who.org_id)
    return AdaCaller(ctx.who.org_id, ctx.who.user_id, 1.0, allowance=allowed)


async def ada(
    ctx: Context, model: str, op: str, args: dict[str, Any], clearance: float | None = None, key: str | None = None
) -> tuple[Any, int | None]:
    """One op of one model, answered by a worker: (answer, the model's active version)."""
    return await send(ctx.ada, await caller(ctx), model, op, args, clearance, keyed(key or ""))


def args_of(body: BaseModel, *left: str) -> dict[str, Any]:
    """A tool's arguments as the op takes them: the model's name, the clearance and anything else named left out."""
    return body.model_dump(exclude_none=True, exclude={"name", "clearance", "idempotency_key", *left})


def pct(p: float) -> str:
    return f"{100 * p:.0f}%"
