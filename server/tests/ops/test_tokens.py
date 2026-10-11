from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unauthorized
from glyphh_server.models import Token
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from tests.db.helpers import make_client, make_org, make_user


async def _member(engine: AsyncEngine, email: str):
    org = await make_org(engine, f"Org of {email}")
    return org, await make_user(engine, org, email, "org_admin")


def test_secrets_are_random_and_only_their_hash_is_kept() -> None:
    a, b = make_secret(), make_secret()
    assert a != b and len(a) >= 43
    assert hash_secret(a) == hash_secret(a) != hash_secret(b) and len(hash_secret(a)) == 64


async def test_an_issued_token_names_its_member_org_role_and_host(engine: AsyncEngine) -> None:
    org, user = await _member(engine, "issue@tok.test")
    host = await make_client(engine, "issue-host")
    async with engine.begin() as conn:
        issued = await tokens.issue(conn, user, host)
        who = await tokens.principal_for(conn, issued.access_token)
        stored = (await conn.execute(select(Token.access_hash).where(Token.user_id == user))).scalar_one()
    assert (who.user_id, who.org_id, who.role, who.oauth_client_id) == (user, org, "org_admin", host)
    assert issued.expires_in == 3600 and issued.token_type == "Bearer"
    assert stored == hash_secret(issued.access_token) != issued.access_token


async def test_unknown_expired_and_revoked_tokens_are_refused_the_same(engine: AsyncEngine) -> None:
    _, user = await _member(engine, "refuse@tok.test")
    async with engine.begin() as conn:
        expired, revoked = await tokens.issue(conn, user), await tokens.issue(conn, user)
        await conn.execute(
            update(Token)
            .where(Token.access_hash == hash_secret(expired.access_token))
            .values(access_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await tokens.revoke(conn, revoked.refresh_token)
        for bad in ("nonsense", expired.access_token, revoked.access_token):
            with pytest.raises(Unauthorized) as caught:
                await tokens.principal_for(conn, bad)
            assert caught.value.code == "E_UNAUTHORIZED"


async def test_a_refresh_rotates_and_works_once(engine: AsyncEngine) -> None:
    _, user = await _member(engine, "rotate@tok.test")
    async with engine.begin() as conn:
        first = await tokens.issue(conn, user)
        second = await tokens.rotate(conn, first.refresh_token)
        assert (await tokens.principal_for(conn, second.access_token)).user_id == user
        with pytest.raises(Unauthorized):
            await tokens.principal_for(conn, first.access_token)
        with pytest.raises(Unauthorized):
            await tokens.rotate(conn, first.refresh_token)


async def test_an_expired_refresh_token_is_refused(engine: AsyncEngine) -> None:
    _, user = await _member(engine, "stale@tok.test")
    async with engine.begin() as conn:
        issued = await tokens.issue(conn, user)
        await conn.execute(
            update(Token)
            .where(Token.refresh_hash == hash_secret(issued.refresh_token))
            .values(refresh_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        with pytest.raises(Unauthorized):
            await tokens.rotate(conn, issued.refresh_token)


async def test_revoking_by_the_access_token_ends_the_pair_and_unknown_is_fine(engine: AsyncEngine) -> None:
    _, user = await _member(engine, "revoke@tok.test")
    async with engine.begin() as conn:
        issued = await tokens.issue(conn, user)
        await tokens.revoke(conn, issued.access_token)
        await tokens.revoke(conn, "never-issued")
        with pytest.raises(Unauthorized):
            await tokens.rotate(conn, issued.refresh_token)
