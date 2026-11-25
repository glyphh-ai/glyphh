from urllib.parse import urlencode

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.providers.upstream import json_call
from glyphh_server.ops.auth.signin import ProviderProfile

NAME: str = "google"
AUTHORIZE: str = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN: str = "https://oauth2.googleapis.com/token"
USERINFO: str = "https://openidconnect.googleapis.com/v1/userinfo"


def configured(cfg: Settings) -> bool:
    return bool(cfg.google_client_id and cfg.google_client_secret)


def authorize_url(cfg: Settings, redirect_uri: str, state: str) -> str:
    query = {
        "client_id": cfg.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTHORIZE}?{urlencode(query)}"


async def profile(http: httpx.AsyncClient, cfg: Settings, code: str, redirect_uri: str) -> ProviderProfile:
    token = await json_call(
        http,
        NAME,
        "POST",
        TOKEN,
        data={
            "code": code,
            "client_id": cfg.google_client_id,
            "client_secret": cfg.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if "access_token" not in token:
        raise Unavailable("Signing in with google didn't work. Try again.", provider=NAME)
    me = await json_call(http, NAME, "GET", USERINFO, headers={"authorization": f"Bearer {token['access_token']}"})
    return ProviderProfile(
        provider="google",
        subject=str(me["sub"]),
        email=me["email"],
        email_verified=bool(me.get("email_verified")),
        name=me.get("name") or " ".join(n for n in (me.get("given_name"), me.get("family_name")) if n) or None,
    )
