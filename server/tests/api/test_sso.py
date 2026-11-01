"""An org's single sign-on by OpenID Connect: set by its admin on Enterprise (the issuer read first, the secret sealed,
a domain one org's), offered on the sign-in pages, a sign-in by work email that lands in that org and nowhere else,
and, enforced, the only way in for the org's people. The suite shares one database, so each test has a domain of
its own."""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Identity, Invite, OrgSso, User
from glyphh_server.ops.auth.providers import oidc
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.auth.signin import OTHER_ORG, SSO_REQUIRED
from tests.api.browser import decide, error_page, new_code, went
from tests.conftest import PROVIDER_SETTINGS, SECRET_KEY, _client
from tests.connector import ask, register
from tests.db.helpers import Person, member, person
from tests.fakes import GOOGLE_ME, FakeStripe, fake_http

IDP: str = "https://idp.test"
DISCOVERY: dict[str, Any] = {
    "issuer": IDP,
    "authorization_endpoint": f"{IDP}/oauth2/authorize",
    "token_endpoint": f"{IDP}/oauth2/token",
    "userinfo_endpoint": f"{IDP}/oauth2/userinfo",
}
CALLBACK: str = "http://localhost:8080/auth/sso/callback"
Answers = dict[tuple[str, str], Any]


def a_domain() -> str:
    return f"{uuid.uuid4().hex[:10]}.test"


def idp_as(email: str, sub: str | None = None, **more: Any) -> Answers:
    """The provider's answers, with this person signed in there."""
    me = {"sub": sub or f"00u-{email}", "email": email, "name": "Pat Lee", **more}
    return {
        ("GET", "/.well-known/openid-configuration"): DISCOVERY,
        ("POST", "/oauth2/token"): {"access_token": "idp-at"},
        ("GET", "/oauth2/userinfo"): me,
    }


def body(domain: str, **over: Any) -> dict[str, Any]:
    return {"issuer": IDP, "client_id": "0oa1", "client_secret": "s3cret", "domains": [domain], **over}


@pytest.fixture(autouse=True)
def fresh() -> Any:
    oidc.forget()
    yield
    oidc.forget()


def app_with(stripe: FakeStripe, over: Answers | None = None) -> AsyncIterator[httpx.AsyncClient]:
    return _client(create_app(PROVIDER_SETTINGS, http=fake_http(stripe, over or idp_as("nobody@idp.test"))))


@pytest.fixture
async def http(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[httpx.AsyncClient]:
    async for c in app_with(stripe):
        yield c


async def set_sso(http: httpx.AsyncClient, who: Person, domain: str, **over: Any) -> dict[str, Any]:
    res = await http.put("/v1/org/sso", json=body(domain, **over), headers=who.headers)
    assert res.status_code == 200, res.text
    return res.json()


async def start(http: httpx.AsyncClient, email: str | None, **purpose: str) -> httpx.Response:
    params = {**purpose, **({"email": email} if email is not None else {})}
    return await http.get("/auth/sso/start", params=params)


async def come_back(http: httpx.AsyncClient, started: httpx.Response) -> httpx.Response:
    assert started.status_code == 302, started.text
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    return await http.get("/auth/sso/callback", params={"code": "c-1", "state": state})


async def google(http: httpx.AsyncClient) -> httpx.Response:
    """The device flow with Google, up to the person's return: where the browser went."""
    code = await new_code(http)
    started = await http.get("/auth/google/start", params={"code": code["user_code"]})
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    return await http.get("/auth/google/callback", params={"code": "c-1", "state": state})


async def device_sign_in(http: httpx.AsyncClient, email: str) -> dict[str, Any]:
    """The device flow by single sign-on, approved: who /v1/me says the install is."""
    code = await new_code(http)
    back = await come_back(http, await start(http, email, code=code["user_code"]))
    path, q = went(back)
    assert path == "/device/approve", path
    shown = (await http.get("/auth/consent", params={"consent": q["consent"]})).json()
    assert shown["email"] == email.strip().lower()
    assert went(await decide(http, q["consent"], "approve")) == ("/device/done", {"result": "approved"})
    token = (await http.post("/v1/device/token", json={"device_code": code["device_code"]})).json()
    me = await http.get("/v1/me", headers={"authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200, me.text
    return me.json()


async def test_the_admin_sets_single_sign_on_and_anyone_in_the_org_reads_it(
    http: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    bob = await member(engine, ada.org_id)
    domain, other = a_domain(), a_domain()
    assert (await http.get("/v1/org/sso", headers=bob.headers)).json() is None
    view = await set_sso(http, ada, domain.upper())
    assert view["issuer"] == IDP and view["client_id"] == "0oa1" and view["domains"] == [domain]
    assert (view["enforced"], view["callback_url"], "client_secret" in view) == (False, CALLBACK, False)
    assert (await http.get("/v1/org/sso", headers=bob.headers)).json() == view
    listed = (await http.get("/auth/providers")).json()
    assert listed["providers"] == ["google", "github"] and listed["sso"] is True
    async with engine.begin() as conn:
        kept = (await conn.execute(select(OrgSso.client_secret).where(OrgSso.org_id == ada.org_id))).scalar_one()
    assert kept.startswith("v1.") and "s3cret" not in kept and unseal(SECRET_KEY, kept) == "s3cret"
    again = await set_sso(http, ada, domain, client_secret=None, domains=[domain, domain.upper(), other], enforced=True)
    assert again["domains"] == sorted([domain, other]) and again["enforced"] is True
    async with engine.begin() as conn:
        kept = (await conn.execute(select(OrgSso.client_secret).where(OrgSso.org_id == ada.org_id))).scalar_one()
    assert unseal(SECRET_KEY, kept) == "s3cret"
    assert (await http.delete("/v1/org/sso", headers=bob.headers)).status_code == 403
    assert (await http.delete("/v1/org/sso", headers=ada.headers)).status_code == 204
    assert (await http.get("/v1/org/sso", headers=ada.headers)).json() is None


async def test_single_sign_on_is_the_admins_on_enterprise_with_a_secret_the_first_time(
    http: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    bob = await member(engine, ada.org_id)
    team = await person(engine, "Team")
    domain = a_domain()
    refused = await http.put("/v1/org/sso", json=body(domain), headers=bob.headers)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "E_FORBIDDEN")
    refused = await http.put("/v1/org/sso", json=body(domain), headers=team.headers)
    assert refused.status_code == 403 and refused.json()["error"] | {"trace_id": ""} == {
        "code": "E_NOT_IN_PLAN",
        "message": "Single sign-on is on Enterprise, not Team: talk to us at sales@glyphh.ai.",
        "reason": "sso",
        "trace_id": "",
    }
    refused = await http.put("/v1/org/sso", json=body(domain, client_secret=None), headers=ada.headers)
    assert (refused.status_code, refused.json()["error"]["reason"]) == (422, "client_secret")
    for bad in ({"issuer": "http://idp.test"}, {"domains": ["not a domain"]}, {"domains": []}):
        assert (await http.put("/v1/org/sso", json=body(domain, **bad), headers=ada.headers)).status_code == 422
    assert (await http.get("/v1/org/sso", headers=ada.headers)).json() is None


async def test_a_wrong_issuer_keeps_nothing_and_a_domain_is_one_orgs(stripe: FakeStripe, engine: AsyncEngine) -> None:
    ada = await person(engine, "Enterprise")
    eve = await person(engine, "Enterprise")
    domain, other = a_domain(), a_domain()
    down = {**idp_as("x@idp.test"), ("GET", "/.well-known/openid-configuration"): httpx.Response(404)}
    async for http in app_with(stripe, down):
        refused = await http.put("/v1/org/sso", json=body(domain), headers=ada.headers)
        assert (refused.status_code, refused.json()["error"]["reason"]) == (503, "discovery")
        assert "could not be read" in refused.json()["error"]["message"]
        assert (await http.get("/v1/org/sso", headers=ada.headers)).json() is None
    async for http in app_with(stripe):
        await set_sso(http, ada, domain)
        taken = await http.put("/v1/org/sso", json=body(other, domains=[other, domain]), headers=eve.headers)
        assert taken.status_code == 409, taken.text
        assert taken.json()["error"]["message"] == f"{domain} is already another organisation's sign-in domain."
        assert (await http.get("/v1/org/sso", headers=eve.headers)).json() is None
        assert (await set_sso(http, eve, other))["domains"] == [other]


async def test_a_person_signs_in_by_work_email_and_lands_in_the_org_as_a_member(
    stripe: FakeStripe, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    domain = a_domain()
    pat = f"pat@{domain}"
    async for http in app_with(stripe, idp_as(pat.capitalize())):  # the provider's own casing of the email
        await set_sso(http, ada, domain)
        invited = await http.post("/v1/org/invites", json={"email": pat}, headers=ada.headers)
        assert invited.status_code == 201
        code = await new_code(http)
        started = await start(http, f" {pat.upper()} ", code=code["user_code"])
        assert started.status_code == 302 and "glyphh_signin" in started.headers["set-cookie"]
        away = urlsplit(started.headers["location"])
        q = parse_qs(away.query)
        assert f"{away.scheme}://{away.netloc}{away.path}" == f"{IDP}/oauth2/authorize"
        assert (q["client_id"], q["redirect_uri"], q["scope"]) == (["0oa1"], [CALLBACK], ["openid email profile"])
        me = await device_sign_in(http, pat)
        assert (me["email"], me["name"], me["role"], me["org"]["id"], me["providers"]) == (
            pat,
            "Pat Lee",
            "member",
            str(ada.org_id),
            ["sso"],
        )
        assert me["plan"]["name"] == "Enterprise"
        again = await device_sign_in(http, pat)  # returning: the same person
        assert again["id"] == me["id"]
        members = (await http.get("/v1/org/members", headers=ada.headers)).json()
        assert [m["email"] for m in members] == [ada.email, pat]
        assert (await http.get("/v1/org/invites", headers=ada.headers)).json() == []  # the invite was taken
    async with engine.begin() as conn:
        taken = (await conn.execute(select(Invite.accepted_at).where(Invite.org_id == ada.org_id))).scalar_one()
    assert taken is not None


async def test_an_existing_member_is_linked_and_anyone_of_another_org_is_refused(
    stripe: FakeStripe, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    domain = a_domain()
    bob = await member(engine, ada.org_id, email=f"bob@{domain}")
    eve = await person(engine, email=f"eve@{domain}")  # her own Free org
    async for http in app_with(stripe, idp_as(bob.email.capitalize())):
        await set_sso(http, ada, domain)
        me = await device_sign_in(http, bob.email)
        assert me["id"] == str(bob.user_id) and me["providers"] == ["sso"]
    async for http in app_with(stripe, idp_as(eve.email)):
        code = await new_code(http)
        back = await come_back(http, await start(http, eve.email, code=code["user_code"]))
        assert error_page(back) | {"trace": ""} == {"code": "E_FORBIDDEN", "message": OTHER_ORG, "trace": ""}
        assert eve.org_id != ada.org_id
    async with engine.begin() as conn:  # bob's SSO account, once bob has left for an org of his own
        await conn.execute(update(User).where(User.id == bob.user_id).values(org_id=eve.org_id))
    async for http in app_with(stripe, idp_as(bob.email.capitalize())):
        code = await new_code(http)
        back = await come_back(http, await start(http, bob.email, code=code["user_code"]))
        assert error_page(back)["message"] == OTHER_ORG


async def test_no_sign_in_for_the_domain_no_email_or_one_since_removed_is_refused(
    http: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    domain, nowhere = a_domain(), a_domain()
    await set_sso(http, ada, domain)
    code = await new_code(http)
    refused = error_page(await start(http, f"x@{nowhere}", code=code["user_code"]))
    assert refused["code"] == "E_NOT_FOUND" and refused["message"].startswith(
        f"No single sign-on is set up for {nowhere}"
    )
    assert error_page(await start(http, None, code=code["user_code"]))["code"] == "E_INVALID"
    assert error_page(await start(http, f"pat@{domain}"))["code"] == "E_INVALID"  # nothing to sign in for
    started = await start(http, f"pat@{domain}", code=code["user_code"])
    assert (await http.delete("/v1/org/sso", headers=ada.headers)).status_code == 204
    gone = error_page(await come_back(http, started))
    assert gone["code"] == "E_INVALID" and gone["message"].startswith("Single sign-on is no longer set up")


async def test_a_secret_sealed_under_another_key_cannot_be_read(http: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Enterprise")
    domain = a_domain()
    await set_sso(http, ada, domain)
    async with engine.begin() as conn:
        other = seal("another-key-of-the-right-length-0123456789abcdef", "s3cret")
        await conn.execute(update(OrgSso).where(OrgSso.org_id == ada.org_id).values(client_secret=other))
    code = await new_code(http)
    refused = error_page(await start(http, f"pat@{domain}", code=code["user_code"]))
    assert refused["code"] == "E_UNAVAILABLE" and "cannot be read" in refused["message"]


async def test_enforced_single_sign_on_refuses_google_for_the_orgs_people_only(
    stripe: FakeStripe, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    domain = a_domain()
    bob = await member(engine, ada.org_id, email=f"bob@{domain}")
    cal = await member(engine, ada.org_id, email=f"cal@{domain}")
    async with engine.begin() as conn:
        await conn.execute(insert(Identity).values(user_id=cal.user_id, provider="google", provider_user_id="g-cal"))
    as_bob = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": "g-bob", "email": bob.email}}
    as_cal = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": "g-cal", "email": cal.email}}
    async for http in app_with(stripe):
        await set_sso(http, ada, domain, enforced=True)
        for over in (as_bob, as_cal):  # linked by email, or returning by Google's id: refused alike
            async for by_google in app_with(stripe, {**idp_as("x@idp.test"), **over}):
                assert error_page(await google(by_google))["message"] == SSO_REQUIRED
        async with engine.begin() as conn:  # nothing was linked to bob
            linked = await conn.execute(select(Identity.provider).where(Identity.user_id == bob.user_id))
            assert list(linked.scalars()) == []
        assert went(await google(http))[0] == "/device/approve"  # a stranger with Google is as welcome as ever
        await set_sso(http, ada, domain, enforced=False)
    async for by_google in app_with(stripe, {**idp_as("x@idp.test"), **as_bob}):  # no longer enforced: linked
        assert went(await google(by_google))[0] == "/device/approve"


async def test_the_connector_is_allowed_with_single_sign_on(stripe: FakeStripe, engine: AsyncEngine) -> None:
    ada = await person(engine, "Enterprise")
    domain = a_domain()
    pat = f"pat@{domain}"
    async for http in app_with(stripe, idp_as(pat)):
        await set_sso(http, ada, domain)
        client = await register(http)
        path, q = went(await http.get("/oauth/authorize", params=ask(client)))
        assert path == "/authorize"
        back = await come_back(http, await start(http, pat, oauth=q["oauth"]))
        path, q = went(back)
        assert path == "/allow"
        shown = (await http.get("/auth/consent", params={"consent": q["consent"]})).json()
        assert (shown["kind"], shown["client"], shown["email"]) == ("oauth", "Claude", pat)
        allowed = await http.get("/auth/oauth/allow", params={"consent": q["consent"], "decision": "allow"})
        assert allowed.status_code == 302 and "code=" in allowed.headers["location"]
    async with engine.begin() as conn:
        org = (await conn.execute(select(User.org_id).where(User.email == pat))).scalar_one()
    assert org == ada.org_id
