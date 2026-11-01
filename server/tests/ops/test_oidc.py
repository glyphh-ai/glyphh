"""An org's OpenID Connect provider: its endpoints found by discovery (kept an hour, refused when wrong), the person
sent to it with the org's client, and who came back read from its userinfo endpoint."""

import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.providers import oidc
from glyphh_server.ops.auth.providers.oidc import Endpoints, Oidc
from tests.conftest import SETTINGS

IDP: str = "https://idp.test"
CB: str = "http://localhost:8080/auth/sso/callback"
DISCOVERY: dict[str, Any] = {
    "issuer": IDP,
    "authorization_endpoint": f"{IDP}/oauth2/authorize",
    "token_endpoint": f"{IDP}/oauth2/token",
    "userinfo_endpoint": f"{IDP}/oauth2/userinfo",
}
ME: dict[str, Any] = {"sub": "00u1", "email": "pat@acme.test", "name": "Pat Lee", "email_verified": True}
ORG: uuid.UUID = uuid.uuid4()


class Idp:
    """The provider at the HTTP layer: what it answers, and every request it saw."""

    def __init__(self, over: dict[tuple[str, str], Any] | None = None) -> None:
        self.answers: dict[tuple[str, str], Any] = {
            ("GET", "/.well-known/openid-configuration"): DISCOVERY,
            ("POST", "/oauth2/token"): {"access_token": "idp-at"},
            ("GET", "/oauth2/userinfo"): ME,
            **(over or {}),
        }
        self.seen: list[httpx.Request] = []
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        found = self.answers[(request.method, request.url.path)]
        return found if isinstance(found, httpx.Response) else httpx.Response(200, json=found)


@pytest.fixture(autouse=True)
def fresh() -> Any:
    oidc.forget()
    yield
    oidc.forget()


def _provider(endpoints: Endpoints | None = None) -> Oidc:
    found = endpoints or Endpoints(
        IDP, DISCOVERY["authorization_endpoint"], DISCOVERY["token_endpoint"], DISCOVERY["userinfo_endpoint"]
    )
    return Oidc(ORG, "0oa1", "s3cret", found)


async def test_discovery_reads_the_issuers_configuration_once_an_hour() -> None:
    idp = Idp()
    found = await oidc.discover(idp.http, IDP + "/")
    assert found == Endpoints(IDP, f"{IDP}/oauth2/authorize", f"{IDP}/oauth2/token", f"{IDP}/oauth2/userinfo")
    assert await oidc.discover(idp.http, IDP) == found and len(idp.seen) == 1
    assert idp.seen[0].url == f"{IDP}/.well-known/openid-configuration"
    oidc.forget()
    await oidc.discover(idp.http, IDP)
    assert len(idp.seen) == 2


@pytest.mark.parametrize(
    "doc",
    [
        {"issuer": IDP, "authorization_endpoint": f"{IDP}/a"},  # no token or userinfo endpoint
        ["not", "an", "object"],
        {**DISCOVERY, "issuer": "https://other.test"},
        {**DISCOVERY, "token_endpoint": "http://idp.test/oauth2/token"},
        httpx.Response(500, text="down"),
    ],
)
async def test_a_configuration_that_is_wrong_or_unreadable_is_unavailable(doc: Any) -> None:
    idp = Idp({("GET", "/.well-known/openid-configuration"): doc})
    with pytest.raises(Unavailable) as refused:
        await oidc.discover(idp.http, IDP)
    assert refused.value.detail["provider"] == "sso"
    assert oidc._found == {}


def test_the_person_is_sent_to_the_issuer_with_the_orgs_client() -> None:
    p = _provider()
    assert p.configured(SETTINGS) is True and Oidc.NAME == "sso"
    url = p.authorize_url(SETTINGS, CB, "st")
    assert url.startswith(f"{IDP}/oauth2/authorize?")
    q = parse_qs(urlsplit(url).query)
    assert (q["client_id"], q["redirect_uri"], q["response_type"], q["scope"], q["state"]) == (
        ["0oa1"],
        [CB],
        ["code"],
        ["openid email profile"],
        ["st"],
    )


async def test_who_came_back_is_read_from_userinfo_with_the_code_exchanged_by_the_client() -> None:
    idp = Idp()
    p = await _provider().profile(idp.http, SETTINGS, "c-1", CB)
    assert (p.provider, p.subject, p.email, p.email_verified, p.name, p.org_id) == (
        "sso",
        f"{IDP}#00u1",
        "pat@acme.test",
        True,
        "Pat Lee",
        ORG,
    )
    exchange, who = idp.seen
    assert exchange.url == f"{IDP}/oauth2/token" and exchange.headers["authorization"].startswith("Basic ")
    assert parse_qs(exchange.content.decode()) == {
        "grant_type": ["authorization_code"],
        "code": ["c-1"],
        "redirect_uri": [CB],
    }
    assert who.headers["authorization"] == "Bearer idp-at"


async def test_a_name_from_its_parts_and_an_email_the_issuer_does_not_vouch_for() -> None:
    parts = {"sub": "00u2", "email": "n@acme.test", "given_name": "Nina", "family_name": "Lee", "email_verified": False}
    p = await _provider().profile(Idp({("GET", "/oauth2/userinfo"): parts}).http, SETTINGS, "c", CB)
    assert (p.name, p.email_verified) == ("Nina Lee", False)
    bare = {"sub": "00u3", "email": "b@acme.test"}
    p = await _provider().profile(Idp({("GET", "/oauth2/userinfo"): bare}).http, SETTINGS, "c", CB)
    assert (p.name, p.email_verified) == (None, True)


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({("POST", "/oauth2/token"): {"error": "invalid_grant"}}, None),
        ({("POST", "/oauth2/token"): ["no"]}, None),
        ({("GET", "/oauth2/userinfo"): {"sub": "00u1"}}, "claims"),
        ({("GET", "/oauth2/userinfo"): ["no"]}, "claims"),
    ],
)
async def test_a_sign_in_the_issuer_does_not_complete_is_unavailable(over: Any, reason: str | None) -> None:
    with pytest.raises(Unavailable) as refused:
        await _provider().profile(Idp(over).http, SETTINGS, "c", CB)
    assert refused.value.detail.get("reason") == reason
