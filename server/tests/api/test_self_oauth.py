"""A registered self-hosted runtime's address is an OAuth resource as a hosted one's is: a sign-in bound to its
`/mcp`, which that runtime's introspection answers active; an address nobody registered is no resource."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.browser import Browser, open_browser
from tests.api.test_runtime_introspect import ask as introspect
from tests.api.test_runtime_introspect import token_of
from tests.connector import allow, ask, exchange, granted, query, register, to_allow
from tests.db.helpers import person
from tests.fakes import FakeStripe
from tests.link import self_runtime

ADDRESS = "https://rrotor.acme.test"


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


async def test_a_registered_self_hosted_address_is_a_resource_bound_to_its_mcp(
    browser: Browser, engine: AsyncEngine
) -> None:
    await self_runtime(engine, await person(engine), ADDRESS)
    claude = await register(browser.http)
    for asked in (ADDRESS, f"{ADDRESS}/mcp", "https://RRotor.acme.test/mcp/"):
        shown, consent = await to_allow(browser.http, ask(claude, resource=asked))
        assert shown["resource"] == f"{ADDRESS}/mcp", asked
    back = query(await allow(browser.http, consent, "allow"))
    res = await exchange(browser.http, claude, back["code"], resource=f"{ADDRESS}/mcp")
    assert res.status_code == 200, res.text
    for bad in (
        "https://elsewhere.acme.test/mcp",
        "http://rrotor.acme.test/mcp",
        f"{ADDRESS}/other",
        f"{ADDRESS}/mcp#x",
        "https:///mcp",
    ):
        back = query(await browser.http.get("/oauth/authorize", params=ask(claude, resource=bad)))
        assert back["error"] == "invalid_target", bad
    res = await exchange(browser.http, claude, "any", resource="https://elsewhere.acme.test")
    assert res.status_code == 400 and res.json()["error"] == "invalid_target"


async def test_the_runtime_introspects_sign_ins_for_its_own_address_only(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    mine = await self_runtime(engine, ada, ADDRESS)
    _, auth = await granted(engine, ada, resource=f"{ADDRESS}/mcp")
    body = (await introspect(client, mine, token_of(auth))).json()
    assert (body["active"], body["sub"]) == (True, str(ada.user_id))
    other = await self_runtime(engine, ada, "https://other.acme.test")
    assert (await introspect(client, other, token_of(auth))).json() == {"active": False}
    _, own = await granted(engine, ada)  # the connector's own: not for any runtime
    assert (await introspect(client, mine, token_of(own))).json() == {"active": False}
