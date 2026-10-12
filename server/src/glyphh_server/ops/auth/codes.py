"""One-time codes for agent hosts. A host's sign-in request rides the sign-in pages as a signed link;
when the member allows it, a code is made (only its hash kept) that works once, for a minute."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit

from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.models import Membership, OAuthClient, OAuthCode
from glyphh_server.ops.auth import hosts, signed
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

CODE_TTL: timedelta = timedelta(minutes=1)
REQUEST_TTL_SECONDS: int = 600


class Pending(BaseModel):
    """A host's sign-in request, waiting for the member to sign in and allow it."""

    client_id: str
    redirect_uri: str
    code_challenge: str
    state: str | None = None
    scopes: list[str] = []
    resource: str | None = None


def pending_link(secret: str, sign_in_url: str, pending: Pending) -> str:
    return f"{sign_in_url}?{urlencode({'request': signed.sign(secret, pending.model_dump(), REQUEST_TTL_SECONDS)})}"


def read_pending(secret: str, token: str) -> Pending:
    body = signed.verify(secret, token)
    body.pop("exp")
    return Pending(**body)


async def approve(conn: AsyncConnection, pending: Pending, user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    """The member allowed the host to act in one of their orgs: make its code, and answer where to send them back."""
    client = await _registered(conn, pending)
    member = select(Membership.user_id).where(
        Membership.user_id == user_id, Membership.org_id == org_id, Membership.disabled_at.is_(None)
    )
    if (await conn.execute(member)).first() is None:
        raise Forbidden("You aren't in that org. Pick one of yours.", reason="not_a_member")
    code = make_secret()
    await conn.execute(
        insert(OAuthCode).values(
            oauth_client_id=client.id,
            user_id=user_id,
            org_id=org_id,
            code_hash=hash_secret(code),
            redirect_uri=pending.redirect_uri,
            code_challenge=pending.code_challenge,
            expires_at=datetime.now(UTC) + CODE_TTL,
        )
    )
    return _back(pending, {"code": code})


async def denied(conn: AsyncConnection, pending: Pending) -> str:
    """The member said no: the host hears access_denied, as OAuth asks, at its own registered address only."""
    await _registered(conn, pending)
    return _back(pending, {"error": "access_denied"})


async def _registered(conn: AsyncConnection, pending: Pending) -> OAuthClient:
    """The host, if it registered this redirect address: never send a member anywhere else."""
    client = await hosts.find(conn, pending.client_id)
    if client is None or pending.redirect_uri not in client.redirect_uris:
        raise Invalid("This app is not registered for that address. Start again from your app.")
    return client


def _back(pending: Pending, answer: dict[str, str]) -> str:
    query = {**answer, **({"state": pending.state} if pending.state else {})}
    parts = urlsplit(pending.redirect_uri)
    return urlunsplit(parts._replace(query="&".join(filter(None, [parts.query, urlencode(query)]))))


async def find(conn: AsyncConnection, oauth_client_id: uuid.UUID, code: str) -> OAuthCode | None:
    row = (
        await conn.execute(
            select(OAuthCode).where(
                OAuthCode.code_hash == hash_secret(code),
                OAuthCode.oauth_client_id == oauth_client_id,
                OAuthCode.used_at.is_(None),
                OAuthCode.expires_at > datetime.now(UTC),
            )
        )
    ).first()
    return None if row is None else OAuthCode(**row._mapping)


async def consume(conn: AsyncConnection, code: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Mark the code used, once, answering who it was for and in which org: a second exchange gets nothing."""
    row = (
        await conn.execute(
            update(OAuthCode)
            .where(OAuthCode.code_hash == hash_secret(code), OAuthCode.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
            .returning(OAuthCode.user_id, OAuthCode.org_id)
        )
    ).first()
    return None if row is None else (row.user_id, row.org_id)
