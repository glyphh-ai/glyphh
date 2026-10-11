from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from glyphh_server.errors import NotFound, Unavailable
from glyphh_server.ops.auth.providers import available, github, google, provider
from tests.conftest import SETTINGS
from tests.fake_providers import GITHUB_USER, PROVIDER_SETTINGS, provider_transport

CB: str = "http://localhost:8080/auth/x/callback"


def _http(over: dict | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=provider_transport(over))


def test_authorize_urls_carry_the_client_callback_and_state() -> None:
    g = parse_qs(urlsplit(google.authorize_url(PROVIDER_SETTINGS, CB, "st")).query)
    assert (g["client_id"], g["redirect_uri"], g["state"], g["scope"]) == (
        ["g-client"],
        [CB],
        ["st"],
        ["openid email profile"],
    )
    h = parse_qs(urlsplit(github.authorize_url(PROVIDER_SETTINGS, CB, "st")).query)
    assert (h["client_id"], h["state"], h["scope"]) == (["gh-client"], ["st"], ["read:user user:email"])


def test_only_configured_providers_are_offered() -> None:
    assert available(PROVIDER_SETTINGS) == ["google", "github"] and available(SETTINGS) == []
    assert provider("github", PROVIDER_SETTINGS) is github
    for name, cfg in (("google", SETTINGS), ("microsoft", PROVIDER_SETTINGS)):
        with pytest.raises(NotFound):
            provider(name, cfg)


async def test_google_profile() -> None:
    p = await google.profile(_http(), PROVIDER_SETTINGS, "code", CB)
    assert (p.subject, p.email, p.email_verified, p.first_name, p.last_name) == (
        "g-pages-1",
        "pages@google.test",
        True,
        "Paige",
        "Turner",
    )


async def test_github_profile_takes_the_primary_verified_email() -> None:
    p = await github.profile(_http(), PROVIDER_SETTINGS, "code", CB)
    assert (p.subject, p.email, p.email_verified, p.first_name, p.last_name) == (
        "4242",
        "octo@gh.test",
        True,
        "Octo",
        "Cat",
    )


async def test_github_without_a_verified_primary_email_is_unverified_and_falls_back_to_the_login() -> None:
    over = {
        ("GET", "/user"): {**GITHUB_USER, "name": None, "email": "public@gh.test"},
        ("GET", "/user/emails"): [{"email": "x@gh.test", "primary": True, "verified": False}],
    }
    p = await github.profile(_http(over), PROVIDER_SETTINGS, "code", CB)
    assert (p.email, p.email_verified, p.first_name, p.last_name) == ("public@gh.test", False, "octo", None)
    bare = {("GET", "/user"): {**GITHUB_USER, "email": None}, ("GET", "/user/emails"): []}
    assert (await github.profile(_http(bare), PROVIDER_SETTINGS, "code", CB)).email == "unknown@github"


@pytest.mark.parametrize(
    "over",
    [
        {("POST", "/token"): {"error": "invalid_grant"}},
        {("POST", "/token"): httpx.Response(500)},
        {("GET", "/v1/userinfo"): httpx.Response(200, text="not json")},
    ],
)
async def test_google_failing_is_unavailable(over: dict) -> None:
    with pytest.raises(Unavailable) as caught:
        await google.profile(_http(over), PROVIDER_SETTINGS, "code", CB)
    assert caught.value.detail == {"provider": "google"}


async def test_github_without_a_token_is_unavailable() -> None:
    with pytest.raises(Unavailable):
        await github.profile(
            _http({("POST", "/login/oauth/access_token"): {"error": "bad_verification_code"}}),
            PROVIDER_SETTINGS,
            "code",
            CB,
        )
