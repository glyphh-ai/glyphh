"""When no plan lifts a limit, the refusal says to free one up instead."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import LimitReached
from glyphh_server.ops import limits
from glyphh_server.ops.plans import newest_version


async def test_past_teams_installs_nothing_lifts_it(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        team = await newest_version(conn, "Team")
        await limits.check(conn, "installs", 9, team)
        with pytest.raises(LimitReached) as refused:
            await limits.check(conn, "installs", 10, team)
    assert refused.value.detail == {"reason": "installs", "limit": "installs", "used": 10, "max": 10, "plan": None}
    assert "Remove one first" in refused.value.message
