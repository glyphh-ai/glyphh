"""Past Team's machines, only Enterprise lifts the limit: the refusal names it."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import LimitReached
from glyphh_server.ops import limits
from glyphh_server.ops.plans import newest_version


async def test_past_teams_machines_enterprise_lifts_it(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        team = await newest_version(conn, "Team")
        await limits.check_machines(conn, 9, team)
        with pytest.raises(LimitReached) as refused:
            await limits.check_machines(conn, 10, team)
        await limits.check_machines(conn, 10**6, await newest_version(conn, "Enterprise"))
    assert refused.value.detail == {
        "reason": "machines",
        "limit": "machines",
        "used": 10,
        "max": 10,
        "plan": "Enterprise",
    }
    assert refused.value.message == "Your Team plan allows 10 hosted machines. Enterprise allows more."
