"""Authorization codes: made when the person allows a client (random, only the hash kept, 2 minutes), redeemed once
by the same client and redirect URI with the PKCE verifier for the S256 challenge (compared in constant time). A code
redeemed a second time revokes the grant it went into (OAuth 2.1 section 4.1.3)."""

import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import OAuthCode
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.connector import grants, tokens
from glyphh_server.ops.connector.authorize import PKCE, AuthorizeRequest
from glyphh_server.ops.connector.errors import invalid_grant
from glyphh_server.ops.connector.tokens import TokenAnswer

CODE_TTL: timedelta = timedelta(minutes=2)


async def issue(conn: AsyncConnection, req: AuthorizeRequest, user_id: uuid.UUID) -> str:
    code = make_secret()
    values = {
        "code_hash": hash_secret(code),
        "client_id": uuid.UUID(req.client_id),
        "user_id": user_id,
        "redirect_uri": req.redirect_uri,
        "code_challenge": req.challenge,
        "scope": req.scope,
        "resource": req.resource,
        "expires_at": datetime.now(UTC) + CODE_TTL,
    }
    await conn.execute(insert(OAuthCode).values(values))
    return code


def pkce_holds(verifier: str | None, challenge: str) -> bool:
    if not verifier or not PKCE.match(verifier):
        return False
    made = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return hmac.compare_digest(made, challenge)


async def redeem(conn: AsyncConnection, client_id: uuid.UUID, form: dict[str, str]) -> TokenAnswer:
    found = select(OAuthCode).where(OAuthCode.code_hash == hash_secret(form.get("code", ""))).with_for_update()
    code = (await conn.execute(found)).first()
    if code is None or code.client_id != client_id:
        raise invalid_grant("The authorization code is not valid.")
    if code.used_at is not None:
        await grants.end(conn, code.grant_id)
        raise invalid_grant("The authorization code was already used: what it issued is revoked.")
    if code.expires_at <= datetime.now(UTC) or form.get("redirect_uri") != code.redirect_uri:
        raise invalid_grant("The authorization code has expired or its redirect_uri doesn't match.")
    if not pkce_holds(form.get("code_verifier"), code.code_challenge):
        raise invalid_grant("The PKCE code_verifier doesn't match the code_challenge.")
    grant_id = await grants.grant_for(conn, code.user_id, client_id, code.scope, code.resource)
    await conn.execute(
        update(OAuthCode).where(OAuthCode.code_hash == code.code_hash).values(used_at=func.now(), grant_id=grant_id)
    )
    return await tokens.issue(conn, grant_id, code.scope)
