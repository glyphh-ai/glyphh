"""One call to the Ada workers as a person signed in to Glyphh, for their templates: their org, full clearance, their
org's plan allowance read in a short transaction of its own, so no connection is held while a worker answers. The
connector's Ada tools call the same way (mcp/tools/ada_base.py)."""

from typing import Any

from glyphh_ada.allowance import allowance
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.api.call import send
from glyphh_server.db import tenancy
from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.principal import Principal

OFF: str = "Templates keep their models in Ada Cloud, which is not on here."


async def caller(state: Any, who: Principal) -> AdaCaller:
    if state is None:
        raise Unavailable(OFF, reason="ada_off")
    async with state.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        allowed = await allowance(conn, who.org_id)
    return AdaCaller(who.org_id, who.user_id, 1.0, allowance=allowed)


async def ask(state: Any, who: Principal, model: str, op: str, args: dict[str, Any]) -> Any:
    """The worker's answer to one op of one model."""
    return (await send(state, await caller(state, who), model, op, args))[0]
