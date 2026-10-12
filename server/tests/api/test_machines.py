"""My machines: their cards, the super powers on each (See all), and opening one with a one-time ticket."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import LaunchTicket
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.auth.secrets import hash_secret
from tests.db.helpers import install, make_machine, make_org, make_user


async def _me(engine: AsyncEngine, email: str) -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
    org = await make_org(engine, f"Machines of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        return org, user, {"authorization": f"Bearer {(await tokens.issue(conn, user, org)).access_token}"}


async def test_cards_show_the_eight_most_recent_and_the_counts(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "cards@machines.test")
    studio = await make_machine(engine, org, user, "studio-mac")
    await make_machine(engine, org, user, "old-laptop", online=False)
    for i in range(10):
        await install(engine, studio, org, user, f"Power {i}", "working" if i < 3 else "idle", minutes_ago=i)
    await install(engine, studio, org, user, "Scout", "needs_you")
    other_org, other, _ = await _me(engine, "someone@machines.test")
    await make_machine(engine, other_org, other, "not-mine")
    page = (await client.get("/v1/machines", headers=auth)).json()
    assert [m["name"] for m in page["machines"]] == ["studio-mac", "old-laptop"]
    assert (page["total"], page["online"]) == (2, 1)
    card = page["machines"][0]
    assert [f["name"] for f in card["super_powers"]] == [f"Power {i}" for i in range(8)]
    assert (card["installed"], card["working"], card["needs_you"]) == (11, 3, 1)
    assert page["machines"][1]["super_powers"] == [] and page["machines"][1]["installed"] == 0
    second = (await client.get("/v1/machines?page=2&size=1", headers=auth)).json()
    assert [m["name"] for m in second["machines"]] == ["old-laptop"]
    assert (await client.get("/v1/machines?size=101", headers=auth)).status_code == 422


async def test_see_all_searches_filters_and_counts(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "all@machines.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    await install(engine, mac, org, user, "Revenue Forecaster", "idle", 5, "Projects next quarter")
    await install(engine, mac, org, user, "Ledger", "working", 1, "Keeps the books tidy, revenue too")
    await install(engine, mac, org, user, "Scout", "needs_you", None, "Wants to post 100%_ sure")
    url = f"/v1/machines/{mac}/super-powers"
    every = (await client.get(url, headers=auth)).json()
    assert every["machine"] == "studio-mac" and [s["name"] for s in every["super_powers"]] == [
        "Ledger",
        "Revenue Forecaster",
        "Scout",
    ]
    assert every["counts"] == {"all": 3, "working": 1, "thinking": 0, "needs_you": 1, "idle": 1, "stuck": 0, "done": 0}
    rev = (await client.get(url, headers=auth, params={"q": " rev "})).json()
    assert [s["name"] for s in rev["super_powers"]] == ["Ledger", "Revenue Forecaster"] and rev["total"] == 2
    assert (await client.get(url, headers=auth, params={"q": "%_"})).json()["total"] == 1
    assert (await client.get(url, headers=auth, params={"status": "working"})).json()["total"] == 1
    paged = (await client.get(url, headers=auth, params={"page": 2, "size": 2})).json()
    assert [s["name"] for s in paged["super_powers"]] == ["Scout"] and paged["total"] == 3
    assert (await client.get(url, headers=auth, params={"status": "asleep"})).status_code == 422
    gone = await client.get(f"/v1/machines/{uuid.uuid4()}/super-powers", headers=auth)
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "E_NOT_FOUND"


async def test_opening_a_machine_gives_a_one_minute_ticket(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "open@machines.test")
    mac = await make_machine(engine, org, user, "studio-mac")
    sp = await install(engine, mac, org, user, "Inbox Zero")
    home = (await client.post(f"/v1/machines/{mac}/open", headers=auth, json={})).json()
    assert home["url"].startswith(f"https://{mac}.glyphh.ai/open?ticket=")
    ticket = home["url"].split("ticket=")[1]
    there = (await client.post(f"/v1/machines/{mac}/open", headers=auth, json={"super_power": str(sp)})).json()
    async with engine.connect() as conn:
        pages = {
            r.token_hash: r.page for r in await conn.execute(select(LaunchTicket).where(LaunchTicket.machine_id == mac))
        }
    assert (
        pages[hash_secret(ticket)] == "home"
        and pages[hash_secret(there["url"].split("ticket=")[1])] == f"super_powers/{sp}"
    )
    stranger = await client.post(f"/v1/machines/{mac}/open", headers=auth, json={"super_power": str(uuid.uuid4())})
    assert stranger.status_code == 404


async def test_an_offline_machine_says_so_when_opened(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    org, user, auth = await _me(engine, "offline@machines.test")
    old = await make_machine(engine, org, user, "old-laptop", online=False)
    res = await client.post(f"/v1/machines/{old}/open", headers=auth, json={})
    assert res.status_code == 409 and res.json()["error"]["reason"] == "offline"
    assert res.json()["error"]["message"] == "old-laptop is offline."
