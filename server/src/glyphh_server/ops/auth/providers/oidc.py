"""Any OpenID Connect provider an org signs in with (Okta, Entra ID, Google Workspace, …), by discovery: the issuer's
`/.well-known/openid-configuration` names its endpoints (kept an hour). The authorization code flow with the org's
client id and secret (HTTP basic at the token endpoint), then the userinfo endpoint says who signed in: no ID token
is parsed, since the code was exchanged over the back channel with the secret. The org's settings are in ops/sso.py;
one of these is made per sign-in, for the org the email's domain names."""

import time
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.providers.upstream import json_call
from glyphh_server.ops.auth.signin import ProviderProfile

NAME: str = "sso"
SCOPE: str = "openid email profile"
WELL_KNOWN: str = "/.well-known/openid-configuration"
KEEP: float = 3600.0
FAILED: str = "Signing in with your organisation's single sign-on didn't work. Try again."


@dataclass(frozen=True)
class Endpoints:
    issuer: str
    authorization: str
    token: str
    userinfo: str


_found: dict[str, tuple[Endpoints, float]] = {}  # each issuer's endpoints, and until when they are kept


def forget() -> None:
    _found.clear()


async def discover(http: httpx.AsyncClient, issuer: str) -> Endpoints:
    """The issuer's endpoints from its OpenID configuration, kept an hour. One that cannot be read, names another
    issuer, or lacks an https authorization, token or userinfo endpoint is Unavailable (`reason` discovery)."""
    issuer = issuer.rstrip("/")
    now = time.monotonic()
    held = _found.get(issuer)
    if held is not None and held[1] > now:
        return held[0]
    doc = await json_call(http, NAME, "GET", issuer + WELL_KNOWN, headers={"accept": "application/json"})
    try:
        found = Endpoints(
            str(doc["issuer"]).rstrip("/"),
            str(doc["authorization_endpoint"]),
            str(doc["token_endpoint"]),
            str(doc["userinfo_endpoint"]),
        )
    except (KeyError, TypeError):
        raise Unavailable(
            f"{issuer}'s OpenID configuration does not name its authorization, token and userinfo endpoints.",
            provider=NAME,
            reason="discovery",
        ) from None
    if found.issuer != issuer or not all(
        u.startswith("https://") for u in (found.authorization, found.token, found.userinfo)
    ):
        raise Unavailable(
            f"{issuer}'s OpenID configuration names another issuer, or an endpoint that is not https.",
            provider=NAME,
            reason="discovery",
        )
    _found[issuer] = (found, now + KEEP)
    return found


@dataclass(frozen=True)
class Oidc:
    """An org's provider, ready to send a person to and to ask who came back: the same steps as Google or GitHub
    (ops/auth/providers, Provider)."""

    NAME: ClassVar[str] = NAME
    org_id: uuid.UUID
    client_id: str
    client_secret: str
    endpoints: Endpoints

    def configured(self, cfg: Settings) -> bool:
        return True

    def authorize_url(self, cfg: Settings, redirect_uri: str, state: str) -> str:
        query = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
        }
        return f"{self.endpoints.authorization}?{urlencode(query)}"

    async def profile(self, http: httpx.AsyncClient, cfg: Settings, code: str, redirect_uri: str) -> ProviderProfile:
        token = await json_call(
            http,
            NAME,
            "POST",
            self.endpoints.token,
            headers={"accept": "application/json"},
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
        if not isinstance(token, dict) or "access_token" not in token:
            raise Unavailable(FAILED, provider=NAME)
        auth = {"authorization": f"Bearer {token['access_token']}", "accept": "application/json"}
        me: Any = await json_call(http, NAME, "GET", self.endpoints.userinfo, headers=auth)
        if not isinstance(me, dict) or not me.get("sub") or not me.get("email"):
            raise Unavailable(
                "Your organisation's sign-in did not say who you are (no subject or email): ask your admin to "
                "grant Glyphh the email claim.",
                provider=NAME,
                reason="claims",
            )
        given = " ".join(n for n in (me.get("given_name"), me.get("family_name")) if n)
        return ProviderProfile(
            provider=NAME,
            subject=f"{self.endpoints.issuer}#{me['sub']}",
            email=str(me["email"]),
            email_verified=bool(me.get("email_verified", True)),
            name=me.get("name") or given or None,
            org_id=self.org_id,
        )
