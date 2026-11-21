"""The connections routes against a faked Pipedream: a link to sign in, a sync adding and removing, the apps, an app's
tools, deleting one, and every route off while Pipedream is not set up."""

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots.pipedream import external_user
from tests.bots.conftest import BOTS, Served, connected, serve
from tests.bots.fakes import SLACK, FakePipedream, account
from tests.conftest import SETTINGS
from tests.db.helpers import person


async def test_a_link_is_pipedreams_page_for_the_org_and_the_app(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await served.http.post("/v1/connections/link", json={"app": "gmail"}, headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "url": "https://pipedream.com/_static/connect.html?token=ctok_1&app=gmail",
        "expires_at": "2026-11-21T12:00:00Z",
    }
    made = next(c for c in served.pd.calls if c[1].endswith("/tokens"))
    assert made[2] == {"external_user_id": external_user(ada.org_id)} == {"external_user_id": f"org_{ada.org_id}"}


async def test_a_sync_adds_the_new_accounts_and_removes_the_gone(served: Served, engine: AsyncEngine) -> None:
    ada, grace = await person(engine), await person(engine)
    gmail = await connected(served, ada)
    assert (gmail["app"], gmail["app_name"], gmail["label"], gmail["app_icon"]) == (
        "gmail",
        "Gmail",
        "ada@gmail.test",
        "g.png",
    )
    served.pd.accounts = [account("apn_2", SLACK, "glyphh")]
    found = (await served.http.post("/v1/connections/sync", headers=ada.headers)).json()["connections"]
    assert [(c["app"], c["account_id"]) for c in found] == [("slack", "apn_2")]
    listed = (await served.http.get("/v1/connections", headers=ada.headers)).json()["connections"]
    assert [c["id"] for c in listed] == [found[0]["id"]]
    assert (await served.http.get("/v1/connections", headers=grace.headers)).json()["connections"] == []


async def test_the_apps_and_a_connections_tools(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    apps = (await served.http.get("/v1/connections/apps", params={"q": "gm"}, headers=ada.headers)).json()
    assert apps == {
        "apps": [{"slug": "gmail", "name": "Gmail", "description": "Email by Google", "icon": "g.png"}],
        "next_cursor": None,
    }
    gmail = await connected(served, ada)
    tools = (await served.http.get(f"/v1/connections/{gmail['id']}/tools", headers=ada.headers)).json()["tools"]
    assert [t["key"] for t in tools] == ["gmail-send-email", "gmail-find-email"]
    grace = await person(engine)
    assert (await served.http.get(f"/v1/connections/{gmail['id']}/tools", headers=grace.headers)).status_code == 404


async def test_deleting_a_connection_deletes_its_account_at_pipedream(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    gmail = await connected(served, ada)
    res = await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)
    assert res.status_code == 204 and served.pd.accounts == []
    assert (await served.http.get("/v1/connections", headers=ada.headers)).json()["connections"] == []
    assert (await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)).status_code == 404


async def test_off_without_pipedream(engine: AsyncEngine) -> None:
    off = BOTS.model_copy(update={"pipedream_client_id": "", "pipedream_project_id": ""})
    async for s in serve(off, FakePipedream()):
        ada = await person(engine)
        for res in (
            await s.http.get("/v1/connections", headers=ada.headers),
            await s.http.post("/v1/connections/link", json={"app": "gmail"}, headers=ada.headers),
            await s.http.get("/v1/connections/apps", headers=ada.headers),
        ):
            assert res.status_code == 503 and res.json()["error"]["reason"] == "pipedream_off"
        assert s.pd.calls == []
    assert not SETTINGS.pipedream_on
