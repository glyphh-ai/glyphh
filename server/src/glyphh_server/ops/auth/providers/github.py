from typing import Any
from urllib.parse import urlencode

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.providers.upstream import json_call
from glyphh_server.ops.auth.signin import ProviderProfile

NAME: str = "github"
AUTHORIZE: str = "https://github.com/login/oauth/authorize"
TOKEN: str = "https://github.com/login/oauth/access_token"
API: str = "https://api.github.com"


def configured(cfg: Settings) -> bool:
    return bool(cfg.github_client_id and cfg.github_client_secret)


def authorize_url(cfg: Settings, redirect_uri: str, state: str) -> str:
    query = {
        "client_id": cfg.github_client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "read:user user:email",
        "allow_signup": "true",
    }
    return f"{AUTHORIZE}?{urlencode(query)}"


def _primary(emails: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((e for e in emails if e.get("primary") and e.get("verified")), None)


async def profile(http: httpx.AsyncClient, cfg: Settings, code: str, redirect_uri: str) -> ProviderProfile:
    token = await json_call(
        http,
        NAME,
        "POST",
        TOKEN,
        headers={"accept": "application/json"},
        data={
            "code": code,
            "client_id": cfg.github_client_id,
            "client_secret": cfg.github_client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    if "access_token" not in token:
        raise Unavailable("Signing in with github didn't work. Try again.", provider=NAME)
    auth = {"authorization": f"Bearer {token['access_token']}", "accept": "application/vnd.github+json"}
    user = await json_call(http, NAME, "GET", f"{API}/user", headers=auth)
    primary = _primary(await json_call(http, NAME, "GET", f"{API}/user/emails", headers=auth))
    return ProviderProfile(
        provider="github",
        subject=str(user["id"]),
        email=primary["email"] if primary else (user.get("email") or "unknown@github"),
        email_verified=primary is not None,
        name=user.get("name") or user.get("login"),
    )
