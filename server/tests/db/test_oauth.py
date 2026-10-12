from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Membership, OAuthClient, OAuthCode, Token
from tests.db.helpers import make_client, make_org, make_user

CHALLENGE: str = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


async def _code(engine: AsyncEngine, client, user, code_hash: str, challenge: str = CHALLENGE) -> None:
    async with engine.begin() as conn:
        org = (await conn.execute(select(Membership.org_id).where(Membership.user_id == user))).scalar_one()
        await conn.execute(
            insert(OAuthCode).values(
                oauth_client_id=client,
                user_id=user,
                org_id=org,
                code_hash=code_hash,
                redirect_uri="http://localhost/cb",
                code_challenge=challenge,
                expires_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )


async def test_a_client_id_is_registered_once_and_needs_a_redirect(engine: AsyncEngine) -> None:
    await make_client(engine, "codex")
    with pytest.raises(IntegrityError):
        await make_client(engine, "codex")
    with pytest.raises(IntegrityError, match="oauth_clients_redirects"):
        async with engine.begin() as conn:
            await conn.execute(insert(OAuthClient).values(client_id="empty", name="Empty", redirect_uris=[]))


async def test_a_code_needs_a_real_pkce_challenge_and_is_unique(engine: AsyncEngine) -> None:
    client = await make_client(engine, "pkce-host")
    user = await make_user(engine, await make_org(engine, "PKCE Co"), "pkce@oauth.test")
    await _code(engine, client, user, "hash-1")
    with pytest.raises(IntegrityError):
        await _code(engine, client, user, "hash-1")
    with pytest.raises(IntegrityError, match="oauth_codes_pkce"):
        await _code(engine, client, user, "hash-2", challenge="too-short")


async def test_removing_a_host_removes_its_codes_and_tokens(engine: AsyncEngine) -> None:
    client = await make_client(engine, "removed-host")
    org = await make_org(engine, "Host Co")
    user = await make_user(engine, org, "host@oauth.test")
    await _code(engine, client, user, "hash-host")
    later = datetime.now(UTC) + timedelta(hours=1)
    async with engine.begin() as conn:
        await conn.execute(
            insert(Token).values(
                user_id=user,
                org_id=org,
                oauth_client_id=client,
                access_hash="a-host",
                refresh_hash="r-host",
                access_expires_at=later,
                refresh_expires_at=later,
            )
        )
        await conn.execute(delete(OAuthClient).where(OAuthClient.id == client))
        codes = (
            await conn.execute(select(func.count()).select_from(OAuthCode).where(OAuthCode.oauth_client_id == client))
        ).scalar()
        tokens = (
            await conn.execute(select(func.count()).select_from(Token).where(Token.access_hash == "a-host"))
        ).scalar()
    assert (codes, tokens) == (0, 0)
