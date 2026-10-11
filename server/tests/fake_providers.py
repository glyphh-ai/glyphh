"""Google and GitHub, faked at the HTTP layer: the server's own code runs unchanged against them."""

from typing import Any

import httpx

from glyphh_server.config import Settings
from tests.conftest import SETTINGS

PROVIDER_SETTINGS: Settings = SETTINGS.model_copy(
    update={
        "google_client_id": "g-client",
        "google_client_secret": "g-secret",
        "github_client_id": "gh-client",
        "github_client_secret": "gh-secret",
    }
)

GOOGLE_ME: dict[str, Any] = {
    "sub": "g-pages-1",
    "email": "pages@google.test",
    "email_verified": True,
    "given_name": "Paige",
    "family_name": "Turner",
    "picture": "https://img.test/p.png",
}
GITHUB_USER: dict[str, Any] = {
    "id": 4242,
    "login": "octo",
    "name": "Octo Cat",
    "avatar_url": "https://img.test/o.png",
    "email": None,
}
GITHUB_EMAILS: list[dict[str, Any]] = [
    {"email": "other@gh.test", "primary": False, "verified": True},
    {"email": "octo@gh.test", "primary": True, "verified": True},
]


def provider_transport(over: dict[tuple[str, str], Any] | None = None) -> httpx.MockTransport:
    answers: dict[tuple[str, str], Any] = {
        ("POST", "/token"): {"access_token": "g-at"},
        ("GET", "/v1/userinfo"): GOOGLE_ME,
        ("POST", "/login/oauth/access_token"): {"access_token": "gh-at"},
        ("GET", "/user"): GITHUB_USER,
        ("GET", "/user/emails"): GITHUB_EMAILS,
        **(over or {}),
    }

    def handle(request: httpx.Request) -> httpx.Response:
        answer = answers[(request.method, request.url.path)]
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=answer)

    return httpx.MockTransport(handle)
