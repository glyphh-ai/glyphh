"""Linking Google or GitHub to a signed-in person's account, so either signs them in; and unlinking one."""

import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from tests.api.browser import error_page, new_code, open_browser, sign_in, went
from tests.conftest import PROVIDER_SETTINGS, PUBLIC_URL, SETTINGS, _client
from tests.db.helpers import an_email, person
from tests.fakes import GITHUB_USER, GOOGLE_ME, FakeStripe, fake_http

LINKED: tuple[str, dict[str, str]] = ("/account", {"linked": "github"})


def _gh_id() -> int:
    return uuid.uuid4().int % 10**9


async def _browser(stripe: FakeStripe, github_id: int) -> AsyncIterator[httpx.AsyncClient]:
    """A browser whose Google account and GitHub account (this id) are a new person's own."""
    email = an_email()
    over = {
        ("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": f"g-{email}", "email": email},
        ("GET", "/user"): {**GITHUB_USER, "id": github_id},
        ("GET", "/user/emails"): [{"email": f"gh-{email}", "primary": True, "verified": True}],
    }
    async for c in _client(create_app(PROVIDER_SETTINGS, http=fake_http(stripe, over))):
        yield c


async def _link_url(http: httpx.AsyncClient, headers: dict[str, str], provider: str = "github") -> str:
    res = await http.post("/v1/me/identities", json={"provider": provider}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["url"]


def _state(started: httpx.Response) -> str:
    return parse_qs(urlsplit(started.headers["location"]).query)["state"][0]


async def _follow(http: httpx.AsyncClient, url: str) -> httpx.Response:
    """Open the link in this browser, go through the provider, come back."""
    started = await http.get(url.removeprefix(PUBLIC_URL))
    assert started.status_code == 302 and "glyphh_signin" in started.headers["set-cookie"], started.text
    provider = urlsplit(url).path.split("/")[2]
    return await http.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": _state(started)})


async def _providers(http: httpx.AsyncClient, headers: dict[str, str]) -> list[str]:
    return (await http.get("/v1/me", headers=headers)).json()["providers"]


async def test_a_person_links_github_then_either_signs_them_in_and_unlinks_one(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    async for b in _browser(stripe, _gh_id()):
        by_google = await sign_in(b)
        url = await _link_url(b, by_google)
        assert url.startswith(f"{PUBLIC_URL}/auth/github/start?link=")
        done = await _follow(b, url)
        assert went(done) == LINKED and 'glyphh_signin=""' in done.headers["set-cookie"]
        assert await _providers(b, by_google) == ["github", "google"]
        again = await b.post("/v1/me/identities", json={"provider": "github"}, headers=by_google)
        assert again.status_code == 409 and again.json()["error"]["code"] == "E_CONFLICT"
        me = (await b.get("/v1/me", headers=by_google)).json()
        await b.post("/v1/sign-out", headers=by_google)
        by_github = await sign_in(b, "github")
        assert (await b.get("/v1/me", headers=by_github)).json()["id"] == me["id"]
        assert (await b.delete("/v1/me/identities/google", headers=by_github)).status_code == 204
        assert await _providers(b, by_github) == ["github"]
        last = await b.delete("/v1/me/identities/github", headers=by_github)
        assert last.status_code == 409 and "only way you sign in" in last.json()["error"]["message"]
        gone = await b.delete("/v1/me/identities/google", headers=by_github)
        assert gone.status_code == 404 and gone.json()["error"]["code"] == "E_NOT_FOUND"
        assert (await b.delete("/v1/me/identities/microsoft", headers=by_github)).status_code == 422
        assert await _providers(b, by_github) == ["github"]


async def test_linking_an_identity_the_person_already_has_says_linked(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine)
    async for b in _browser(stripe, _gh_id()):
        first, second = await _link_url(b, ada.headers), await _link_url(b, ada.headers)
        assert went(await _follow(b, first)) == LINKED
        assert went(await _follow(b, second)) == LINKED
        assert await _providers(b, ada.headers) == ["github"]


async def test_a_github_account_that_is_someone_elses_is_refused_and_nothing_changes(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    github_id = _gh_id()
    async for owner in _browser(stripe, github_id):
        await sign_in(owner, "github")
    ada = await person(engine)
    async for b in _browser(stripe, github_id):
        res = error_page(await _follow(b, await _link_url(b, ada.headers)))
        assert res["code"] == "E_CONFLICT" and "That GitHub account is already its own Glyphh account" in res["message"]
        assert "delete that account first, or contact support" in res["message"]
        assert await _providers(b, ada.headers) == []


async def test_a_second_github_account_is_refused(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine)
    async for one in _browser(stripe, _gh_id()):
        first, second = await _link_url(one, ada.headers), await _link_url(one, ada.headers)
        assert went(await _follow(one, first)) == LINKED
    async for two in _browser(stripe, _gh_id()):
        res = error_page(await _follow(two, second))
        assert res["code"] == "E_CONFLICT" and "Another GitHub account is already linked" in res["message"]
        assert await _providers(two, ada.headers) == ["github"]


async def test_link_steps_that_are_not_right_are_refused(
    engine: AsyncEngine, stripe: FakeStripe, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    url = await _link_url(client, ada.headers, "google")
    value = parse_qs(urlsplit(url).query)["link"][0]
    code = await new_code(client)
    device_state = _state(await client.get("/auth/google/start", params={"code": code["user_code"]}))
    for name, link in (("github", value), ("google", device_state), ("google", "forged.0")):
        res = await client.get(f"/auth/{name}/start", params={"link": link})
        assert error_page(res)["code"] == "E_INVALID", (name, link)
    state = _state(await client.get(url.removeprefix(PUBLIC_URL)))
    async for stranger in _browser(stripe, _gh_id()):
        res = await stranger.get("/auth/google/callback", params={"code": "c", "state": state})
        assert "another browser" in error_page(res)["message"]
    bad = await client.post("/v1/me/identities", json={"provider": "microsoft"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "E_INVALID"
    assert (await client.post("/v1/me/identities", json={"provider": "google"})).status_code == 401


async def test_a_provider_this_server_does_not_offer_cannot_be_linked(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine)
    async for bare in open_browser(stripe, SETTINGS):
        res = await bare.http.post("/v1/me/identities", json={"provider": "github"}, headers=ada.headers)
        assert res.status_code == 404 and res.json()["error"]["code"] == "E_NOT_FOUND"
