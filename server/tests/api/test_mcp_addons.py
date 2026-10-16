"""The connector's add-on tools: the catalog, and adding or removing a mod in two calls, the first only showing the
prorated price; plan shows the add-ons; upgrade checks out with add-ons."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.addons import on_stripe, org_addons
from tests.api.test_mcp_tools import _refused
from tests.connector import granted, tool
from tests.db.helpers import member, person
from tests.fakes import FakeStripe


async def test_addons_lists_the_catalog_for_the_plan(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    listed = await tool(client, auth, "addons")
    assert [a["mod"] for a in listed["structuredContent"]["addons"]] == ["ada"]
    text = listed["content"][0]["text"]
    assert "ada: $4.00 per seat a month ($4.00 for you), not sold with your plan" in text


async def test_add_mod_shows_the_price_first_then_adds_on_confirm_and_remove_mod_the_same(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada, sub = await on_stripe(engine, stripe, "Pro")
    _, auth = await granted(engine, ada)
    asked = await tool(client, auth, "add_mod", mod="ada")
    preview = asked["structuredContent"]["preview"]
    assert asked["structuredContent"]["confirm_needed"] is True and preview["prorated_cents"] == 200
    assert asked["content"][0]["text"].startswith("Adding ada changes your next invoice by $2.00 now, prorated; ")
    assert f"proration_date {preview['proration_date']}" in asked["content"][0]["text"]
    assert await org_addons(engine, ada.org_id) == {}
    done = await tool(client, auth, "add_mod", mod="ada", confirm=True, proration_date=preview["proration_date"])
    assert done["content"][0]["text"] == "ada is added, prorated."
    assert next(a for a in done["structuredContent"]["addons"] if a["mod"] == "ada")["added"] is True
    plan = await tool(client, auth, "plan")
    assert "Add-ons: ada (1)." in plan["content"][0]["text"]
    assert [a["mod"] for a in plan["structuredContent"]["addons"]] == ["ada"]
    listed = (await tool(client, auth, "addons"))["content"][0]["text"]
    assert "ada: $4.00 per seat a month ($4.00 for you), added; models 3, precedents 10000" in listed
    back = await tool(client, auth, "remove_mod", mod="ada")
    assert back["content"][0]["text"].startswith("Removing ada changes your next invoice by -$2.00 now")
    assert "call remove_mod again" in back["content"][0]["text"]
    gone = await tool(client, auth, "remove_mod", mod="ada", confirm=True)
    assert gone["content"][0]["text"] == "ada is removed, prorated."
    assert await org_addons(engine, ada.org_id) == {"ada": ("removed", None, 1)}
    assert len(stripe.subs[sub]["items"]["data"]) == 1


async def test_the_addon_tools_refuse_as_tool_errors(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    free = await person(engine)
    _, auth = await granted(engine, free)
    assert _refused(await tool(client, auth, "add_mod", mod="ada"), "E_CONFLICT")["reason"] == "not_subscribed"
    ada, _ = await on_stripe(engine, stripe, "Pro")
    _, theirs = await granted(engine, await member(engine, ada.org_id))
    _refused(await tool(client, theirs, "remove_mod", mod="ada", confirm=True), "E_FORBIDDEN")
    _refused(await tool(client, auth, "add_mod"), "E_INVALID")


async def test_upgrade_checks_out_with_addons(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    opened = await tool(client, auth, "upgrade", plan="Pro", addons=["ada"])
    assert opened["content"][0]["text"].startswith("Open Stripe Checkout to subscribe to Pro and ada with 1 seats")
    session = stripe.calls[-1][2]
    assert [session[f"line_items[{i}][price]"] for i in range(2)] == ["price_test_pro", "price_test_ada"]
