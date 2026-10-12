from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.models import OAuthCode
from glyphh_server.ops.auth import codes
from glyphh_server.ops.auth.codes import Pending
from glyphh_server.ops.auth.secrets import hash_secret
from tests.conftest import SECRET_KEY
from tests.db.helpers import make_client, make_org, make_user

CHALLENGE: str = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
REDIRECT: str = "http://localhost:33418/callback"


def _pending(client_id: str, redirect: str = REDIRECT, state: str | None = "s1") -> Pending:
    return Pending(client_id=client_id, redirect_uri=redirect, code_challenge=CHALLENGE, state=state)


def test_a_pending_request_rides_a_signed_link() -> None:
    link = codes.pending_link(SECRET_KEY, "http://localhost:8080/auth/sign-in", _pending("c1"))
    assert link.startswith("http://localhost:8080/auth/sign-in?request=")
    token = parse_qs(urlsplit(link).query)["request"][0]
    assert codes.read_pending(SECRET_KEY, token) == _pending("c1")


async def test_allowing_makes_a_code_that_works_once(engine: AsyncEngine) -> None:
    host = await make_client(engine, "codes-host")
    org = await make_org(engine, "Codes Co")
    user = await make_user(engine, org, "codes@ops.test")
    async with engine.begin() as conn:
        back = await codes.approve(conn, _pending("codes-host"), user, org)
        query = parse_qs(urlsplit(back).query)
        code = query["code"][0]
        assert back.startswith(REDIRECT) and query["state"] == ["s1"]
        found = await codes.find(conn, host, code)
        assert found is not None and found.user_id == user and found.code_challenge == CHALLENGE
        assert await codes.consume(conn, code) == (user, org)
        assert await codes.consume(conn, code) is None
        assert await codes.find(conn, host, code) is None


async def test_a_redirect_keeps_its_own_query_and_no_state_is_sent_when_none(engine: AsyncEngine) -> None:
    await make_client(engine, "query-host")
    async with engine.begin() as conn:
        from sqlalchemy import update as upd

        from glyphh_server.models import OAuthClient

        await conn.execute(
            upd(OAuthClient)
            .where(OAuthClient.client_id == "query-host")
            .values(redirect_uris=["http://localhost:1/cb?app=1"])
        )
    org = await make_org(engine, "Query Co")
    user = await make_user(engine, org, "query@ops.test")
    async with engine.begin() as conn:
        back = await codes.approve(conn, _pending("query-host", "http://localhost:1/cb?app=1", None), user, org)
    query = parse_qs(urlsplit(back).query)
    assert query["app"] == ["1"] and "code" in query and "state" not in query


async def test_an_unknown_host_or_an_unregistered_redirect_is_refused(engine: AsyncEngine) -> None:
    await make_client(engine, "strict-host")
    org = await make_org(engine, "Strict Co")
    user = await make_user(engine, org, "strict@ops.test")
    async with engine.begin() as conn:
        for pending in (_pending("nobody"), _pending("strict-host", "https://evil.test/cb")):
            with pytest.raises(Invalid, match="not registered"):
                await codes.approve(conn, pending, user, org)


async def test_an_expired_code_is_not_found(engine: AsyncEngine) -> None:
    host = await make_client(engine, "late-host")
    org = await make_org(engine, "Late Co")
    user = await make_user(engine, org, "late@ops.test")
    async with engine.begin() as conn:
        code = parse_qs(urlsplit(await codes.approve(conn, _pending("late-host"), user, org)).query)["code"][0]
        await conn.execute(
            update(OAuthCode)
            .where(OAuthCode.code_hash == hash_secret(code))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        assert await codes.find(conn, host, code) is None


async def test_a_code_is_only_for_an_org_the_member_is_in(engine: AsyncEngine) -> None:
    from glyphh_server.errors import Forbidden

    await make_client(engine, "member-host")
    org = await make_org(engine, "Mine Co")
    user = await make_user(engine, org, "mine@ops.test")
    stranger = await make_org(engine, "Not Mine Co")
    async with engine.begin() as conn:
        with pytest.raises(Forbidden) as caught:
            await codes.approve(conn, _pending("member-host"), user, stranger)
    assert caught.value.detail == {"reason": "not_a_member"}
