"""Approving or denying a code that is no longer waiting is refused."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.ops import device_approval
from tests.db.helpers import person


async def test_a_code_that_is_not_waiting_cannot_be_approved_or_denied(engine: AsyncEngine) -> None:
    ada = await person(engine)
    async with engine.begin() as conn:
        with pytest.raises(Invalid):
            await device_approval.approve(conn, "BBBB-BBBB", ada.user_id)
        with pytest.raises(Invalid):
            await device_approval.deny(conn, "BBBB-BBBB")
