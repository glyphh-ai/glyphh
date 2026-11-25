"""Single sign-on, per org (Enterprise): the org's admin sets an OpenID Connect issuer, a client id and secret
(sealed at rest, never shown back), the email domains that route a sign-in to it, and whether its people must use
it (the platform's Settings → Auth; `/v1/org/sso`). Setting it reads the issuer's OpenID configuration first, so a
wrong issuer is refused before anything is kept. A person signs in with it from the platform's sign-in pages by
their work email (`/auth/sso/start?email=`): the domain names the org, the org's provider takes them in and brings
them back, and they land in that org and nowhere else (ops/auth/signin.py)."""

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import httpx
from cryptography.exceptions import InvalidTag
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.db.seed import SALES
from glyphh_server.errors import Invalid, NotFound, NotInPlan, Unavailable
from glyphh_server.models import OrgSso, SsoDomain
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.providers import oidc
from glyphh_server.ops.auth.providers.oidc import Oidc
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.guards import require_admin, taken
from glyphh_server.ops.plans import org_version

log = logging.getLogger("glyphh.sso")

NAME: str = oidc.NAME
DOMAINS_MAX: int = 20
DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
NO_SSO: str = "No single sign-on is set up for {domain}. Sign in with Google or GitHub, or ask your admin."
GONE: str = "Single sign-on is no longer set up for your organisation. Start again."


class SsoIn(BaseModel):
    """What the admin sets: the issuer (its OpenID configuration is at `{issuer}/.well-known/openid-configuration`),
    the client Glyphh is registered as there, with the callback `{server}/auth/sso/callback`, and the domains."""

    issuer: str = Field(pattern=r"^https://[^\s/?#]+(?:/[^\s?#]*)?$", max_length=500)
    client_id: str = Field(min_length=1, max_length=500)
    client_secret: str | None = Field(None, min_length=1, max_length=2000, description="Left out: keep the one set")
    domains: list[str] = Field(min_length=1, max_length=DOMAINS_MAX)
    enforced: bool = Field(False, description="The org's people sign in with it and nothing else")

    @field_validator("domains")
    @classmethod
    def _domains(cls, given: list[str]) -> list[str]:
        out: list[str] = []
        for raw in given:
            domain = raw.strip().lower()
            if not DOMAIN.match(domain):
                raise ValueError(f"{raw.strip()} is not a domain (acme.com).")
            if domain not in out:
                out.append(domain)
        return out


class SsoView(BaseModel):
    issuer: str
    client_id: str
    domains: list[str]
    enforced: bool
    callback_url: str = Field(description="The redirect URI to register at the identity provider")
    updated_at: datetime


def callback_url(settings: Settings) -> str:
    return f"{settings.base_url}/auth/{NAME}/callback"


async def view(conn: AsyncConnection, org_id: uuid.UUID, settings: Settings) -> SsoView | None:
    row = (
        await conn.execute(
            select(OrgSso.issuer, OrgSso.client_id, OrgSso.enforced, OrgSso.updated_at).where(OrgSso.org_id == org_id)
        )
    ).first()
    if row is None:
        return None
    domains = await conn.execute(select(SsoDomain.domain).where(SsoDomain.org_id == org_id).order_by(SsoDomain.domain))
    return SsoView(**row._mapping, domains=list(domains.scalars()), callback_url=callback_url(settings))


async def get_sso(conn: AsyncConnection, who: Principal, settings: Settings) -> SsoView | None:
    return await view(conn, who.org_id, settings)


async def set_sso(
    conn: AsyncConnection, who: Principal, settings: Settings, http: httpx.AsyncClient, body: SsoIn
) -> SsoView:
    """Set or change the org's single sign-on: the admin's, on a plan with it (Enterprise). The issuer's OpenID
    configuration is read first (refused as it says, nothing kept); a domain that is another org's is E_CONFLICT."""
    require_admin(who)
    plan = await org_version(conn, who.org_id)
    if not plan.sso:
        raise NotInPlan(f"Single sign-on is on Enterprise, not {plan.name}: talk to us at {SALES}.", reason="sso")
    endpoints = await oidc.discover(http, body.issuer)
    kept = (await conn.execute(select(OrgSso.client_secret).where(OrgSso.org_id == who.org_id))).scalar_one_or_none()
    if body.client_secret is None and kept is None:
        raise Invalid("Enter the client secret from your identity provider.", reason="client_secret")
    values: dict[str, Any] = {
        "issuer": endpoints.issuer,
        "client_id": body.client_id,
        "client_secret": seal(settings.secret_key, body.client_secret) if body.client_secret else kept,
        "enforced": body.enforced,
        "updated_at": func.now(),
    }
    await conn.execute(
        upsert(OrgSso).values(org_id=who.org_id, **values).on_conflict_do_update(index_elements=["org_id"], set_=values)
    )
    await conn.execute(delete(SsoDomain).where(SsoDomain.org_id == who.org_id))
    for domain in body.domains:
        with taken(f"{domain} is already another organisation's sign-in domain.", domain=domain):
            await conn.execute(insert(SsoDomain).values(domain=domain, org_id=who.org_id))
    log.info("sso set", extra=fields(org=str(who.org_id), issuer=endpoints.issuer, enforced=body.enforced))
    found = await view(conn, who.org_id, settings)
    assert found is not None
    return found


async def remove_sso(conn: AsyncConnection, who: Principal) -> None:
    """Single sign-on off: its people sign in with Google or GitHub again (their SSO identities stay, unused)."""
    require_admin(who)
    await conn.execute(delete(OrgSso).where(OrgSso.org_id == who.org_id))
    log.info("sso removed", extra=fields(org=str(who.org_id)))


async def offered(conn: AsyncConnection) -> bool:
    """Whether any org signs in with single sign-on: the sign-in pages offer it then."""
    return (await conn.execute(select(func.count()).select_from(OrgSso))).scalar_one() > 0


async def for_email(conn: AsyncConnection, http: httpx.AsyncClient, settings: Settings, email: str) -> Oidc:
    """The provider of the org whose sign-in domain the work email is at."""
    domain = email.strip().lower().rpartition("@")[2]
    if not domain:
        raise Invalid("Enter your work email to sign in with single sign-on.", reason="email")
    row = (
        await conn.execute(
            select(OrgSso.org_id, OrgSso.issuer, OrgSso.client_id, OrgSso.client_secret)
            .join(SsoDomain, SsoDomain.org_id == OrgSso.org_id)
            .where(SsoDomain.domain == domain)
        )
    ).first()
    if row is None:
        raise NotFound(NO_SSO.format(domain=domain), reason="no_sso", domain=domain)
    return await _ready(http, settings, row)


async def for_org(conn: AsyncConnection, http: httpx.AsyncClient, settings: Settings, org_id: uuid.UUID) -> Oidc:
    """The org's provider, for the person coming back from it."""
    row = (
        await conn.execute(
            select(OrgSso.org_id, OrgSso.issuer, OrgSso.client_id, OrgSso.client_secret).where(OrgSso.org_id == org_id)
        )
    ).first()
    if row is None:
        raise Invalid(GONE, reason="no_sso")
    return await _ready(http, settings, row)


async def _ready(http: httpx.AsyncClient, settings: Settings, row: Row) -> Oidc:
    endpoints = await oidc.discover(http, row.issuer)
    try:
        secret = unseal(settings.secret_key, row.client_secret)
    except (ValueError, InvalidTag):
        raise Unavailable(
            "Your organisation's single sign-on secret cannot be read: its admin must set it again.",
            provider=NAME,
            reason="secret",
        ) from None
    return Oidc(row.org_id, row.client_id, secret, endpoints)
