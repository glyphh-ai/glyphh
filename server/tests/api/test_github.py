"""Installing the Glyphh GitHub App: a link from the API, GitHub's install page in the browser, and the installation
recorded for the person only from the browser that started it and only when it is on their own GitHub account."""

import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Identity
from tests.api.browser import error_page, went
from tests.conftest import PROVIDER_SETTINGS, PUBLIC_URL, _client
from tests.db.helpers import Person, person
from tests.fakes import FakeGitHubApp, FakeStripe, fake_http


def _id() -> int:
    return uuid.uuid4().int % 10**9


async def _with_github(engine: AsyncEngine) -> tuple[Person, int]:
    """A person who signs in with a GitHub account: its id."""
    who, account = await person(engine), _id()
    async with engine.begin() as conn:
        values = {"user_id": who.user_id, "provider": "github", "provider_user_id": str(account)}
        await conn.execute(insert(Identity).values(values))
    return who, account


async def _browser(stripe: FakeStripe, github_app: FakeGitHubApp) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(PROVIDER_SETTINGS, http=fake_http(stripe, github_app=github_app))):
        yield c


async def _to_github(http: httpx.AsyncClient, headers: dict[str, str]) -> str:
    """Ask for the link, open it in this browser: the state GitHub will send back."""
    made = await http.post("/v1/github/install", headers=headers)
    assert made.status_code == 200, made.text
    url = made.json()["url"]
    assert url.startswith(f"{PUBLIC_URL}/v1/github/install?link=")
    away = await http.get(url.removeprefix(PUBLIC_URL))
    assert away.status_code == 302 and "Path=/v1/github" in away.headers["set-cookie"], away.text
    location = urlsplit(away.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "https://github.com/apps/glyphh-test/installations/new"
    )
    return parse_qs(location.query)["state"][0]


async def _back(http: httpx.AsyncClient, state: str, installation_id: int | None) -> httpx.Response:
    params: dict[str, object] = {"state": state, "setup_action": "install"}
    if installation_id is not None:
        params["installation_id"] = installation_id
    return await http.get("/v1/github/callback", params=params)


async def test_a_person_installs_the_app_on_their_account_and_again_later(
    engine: AsyncEngine, client: httpx.AsyncClient, github_app: FakeGitHubApp
) -> None:
    ada, account = await _with_github(engine)
    first, second = _id(), _id()
    github_app.install(first, account, "ada-gh")
    github_app.install(second, account, "ada-gh")
    done = await _back(client, await _to_github(client, ada.headers), first)
    assert went(done) == ("/github", {"installed": "ada-gh"}) and 'glyphh_signin=""' in done.headers["set-cookie"]
    listed = (await client.get("/v1/github/installations", headers=ada.headers)).json()
    assert [(i["installation_id"], i["account_login"], i["removed_at"]) for i in listed] == [(first, "ada-gh", None)]
    assert went(await _back(client, await _to_github(client, ada.headers), second))[1] == {"installed": "ada-gh"}
    listed = (await client.get("/v1/github/installations", headers=ada.headers)).json()
    assert [i["installation_id"] for i in listed] == [second]
    assert github_app.calls == [
        ("GET", f"/app/installations/{first}", None),
        ("GET", f"/app/installations/{second}", None),
    ]


async def test_someone_elses_installation_is_never_recorded(
    engine: AsyncEngine, client: httpx.AsyncClient, github_app: FakeGitHubApp, stripe: FakeStripe
) -> None:
    ada, account = await _with_github(engine)
    eve, eve_account = await _with_github(engine)
    hers = _id()
    github_app.install(hers, eve_account, "eve-gh")
    res = error_page(await _back(client, await _to_github(client, ada.headers), hers))
    assert res["code"] == "E_FORBIDDEN" and "not on the GitHub account you sign in with" in res["message"]
    state = await _to_github(client, ada.headers)
    async for stranger in _browser(stripe, github_app):
        assert "another browser" in error_page(await _back(stranger, state, hers))["message"]
    eve_state = await _to_github(client, eve.headers)
    assert went(await _back(client, eve_state, hers))[1] == {"installed": "eve-gh"}
    assert (await client.get("/v1/github/installations", headers=ada.headers)).json() == []
    github_app.install(hers, account, "shared")  # GitHub now says it is Ada's: it is still Eve's on Glyphh
    res = error_page(await _back(client, await _to_github(client, ada.headers), hers))
    assert res["code"] == "E_CONFLICT" and "another Glyphh account" in res["message"]


async def test_install_steps_that_are_not_right_are_refused(
    engine: AsyncEngine, client: httpx.AsyncClient, github_app: FakeGitHubApp
) -> None:
    ada, _ = await _with_github(engine)
    state = await _to_github(client, ada.headers)
    link = (await client.post("/v1/github/install", headers=ada.headers)).json()["url"].split("link=")[1]
    for res in (
        await client.get("/v1/github/install", params={"link": state}),
        await client.get("/v1/github/install", params={"link": "forged.0"}),
        await _back(client, link, _id()),
        await _back(client, state, None),
    ):
        assert error_page(res)["code"] == "E_INVALID"
    res = error_page(await _back(client, await _to_github(client, ada.headers), _id()))
    assert res["code"] == "E_NOT_FOUND" and "no such installation" in res["message"]
    github_app.fail = True
    res = error_page(await _back(client, await _to_github(client, ada.headers), _id()))
    assert res["code"] == "E_UNAVAILABLE" and "answer. Try again" in res["message"]


async def test_the_link_needs_github_linked_and_the_app_set_up(engine: AsyncEngine, client: httpx.AsyncClient) -> None:
    bob = await person(engine)
    res = await client.post("/v1/github/install", headers=bob.headers)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_not_linked"
    assert (await client.post("/v1/github/install")).status_code == 401
    assert (await client.get("/v1/github/installations")).status_code == 401
    ada, _ = await _with_github(engine)
    link = (await client.post("/v1/github/install", headers=ada.headers)).json()["url"].removeprefix(PUBLIC_URL)
    off = PROVIDER_SETTINGS.model_copy(update={"github_app_slug": ""})
    async for bare in _client(create_app(off, http=fake_http())):
        res = await bare.post("/v1/github/install", headers=ada.headers)
        assert res.status_code == 503 and res.json()["error"]["code"] == "E_UNAVAILABLE"
        assert "set up on this server" in error_page(await bare.get(link))["message"]
