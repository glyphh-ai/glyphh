from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.browser import Browser, Staff, open_browser, open_staff
from tests.fakes import FakeStripe


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


@pytest.fixture
async def staff(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Staff]:
    async for s in open_staff(engine, stripe):
        yield s
