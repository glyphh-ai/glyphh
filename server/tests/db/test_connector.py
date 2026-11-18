"""The connector's tables: clients belong to no org; grants, their tokens and codes are seen only by their own org,
one live grant per person and client, and only known values are kept."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import ConnectorGrant, ConnectorToken, OAuthClient, OAuthCode
from tests.db.helpers import Person, person

LATER: datetime = datetime.now(UTC) + timedelta(hours=1)


async def _client(engine: AsyncEngine, **over: object) -> uuid.UUID:
    values = {"name": "Claude", "redirect_uris": ["https://claude.ai/cb"], "auth_method": "none"}
    async with engine.begin() as conn:
        made = insert(OAuthClient).values(**values | {"grant_types": ["authorization_code"]} | over)
        return (await conn.execute(made.returning(OAuthClient.id))).scalar_one()


async def _granted(engine: AsyncEngine, who: Person, client_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        values = {"user_id": who.user_id, "client_id": client_id, "scope": "account", "resource": "r"}
        grant_id = (await conn.execute(insert(ConnectorGrant).values(values).returning(ConnectorGrant.id))).scalar_one()
        token = {"grant_id": grant_id, "kind": "access", "token_hash": f"t-{grant_id}", "expires_at": LATER}
        await conn.execute(insert(ConnectorToken).values(token))
        code = {"code_hash": f"c-{grant_id}", "client_id": client_id, "user_id": who.user_id, "redirect_uri": "u"}
        code |= {"code_challenge": "x", "scope": "account", "resource": "r", "expires_at": LATER}
        await conn.execute(insert(OAuthCode).values(code))
    return grant_id


async def test_each_org_sees_only_its_own_grants_tokens_and_codes(engine: AsyncEngine) -> None:
    client_id = await _client(engine)
    ada, eve = await person(engine), await person(engine)
    for who in (ada, eve):
        await _granted(engine, who, client_id)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        for table, own in ((ConnectorGrant, 2), (ConnectorToken, 3), (OAuthCode, 1)):  # with her platform sign-in's
            assert (await conn.execute(select(func.count()).select_from(table))).scalar_one() == own, table
        seen = await conn.execute(select(OAuthClient.id).where(OAuthClient.id == client_id))
        assert seen.scalar_one() == client_id


async def _refused(engine: AsyncEngine, constraint: str, table: type, **values: object) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        async with engine.begin() as conn:
            await conn.execute(insert(table).values(**values))


async def test_one_live_grant_per_person_and_client_and_only_known_values(engine: AsyncEngine) -> None:
    client_id, ada = await _client(engine), await person(engine)
    grant_id = await _granted(engine, ada, client_id)
    again = {"user_id": ada.user_id, "client_id": client_id, "scope": "account", "resource": "r"}
    await _refused(engine, "connector_grants_user_client", ConnectorGrant, **again)
    async with engine.begin() as conn:
        await conn.execute(update(ConnectorGrant).where(ConnectorGrant.id == grant_id).values(revoked_at=func.now()))
        await conn.execute(insert(ConnectorGrant).values(again))
    token = {"grant_id": grant_id, "kind": "id", "token_hash": "kind", "expires_at": LATER}
    await _refused(engine, "connector_tokens_kind", ConnectorToken, **token)
    plain = {"name": "x", "redirect_uris": ["https://x.test/cb"], "grant_types": ["authorization_code"]}
    await _refused(engine, "oauth_clients_secret", OAuthClient, **plain, auth_method="client_secret_post")
    await _refused(engine, "oauth_clients_auth_method", OAuthClient, **plain, auth_method="tls", secret_hash="h")
    await _refused(
        engine, "oauth_clients_redirect_uris", OAuthClient, **plain | {"redirect_uris": []}, auth_method="none"
    )
