"""The provider's refusals that the SDK's routes never reach on their own: called directly."""

import pytest
from mcp.server.auth.provider import AuthorizationCode, RefreshToken, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unauthorized
from glyphh_server.mcp.oauth import GlyphhOAuth
from glyphh_server.mcp.principal import current_principal
from tests.conftest import PUBLIC_URL, SECRET_KEY

CLIENT = OAuthClientInformationFull(client_id="ghost", redirect_uris=["http://localhost/cb"])


def _provider(engine: AsyncEngine) -> GlyphhOAuth:
    return GlyphhOAuth(engine, PUBLIC_URL, SECRET_KEY)


async def test_an_unknown_host_has_no_codes_and_a_used_code_trades_for_nothing(engine: AsyncEngine) -> None:
    provider = _provider(engine)
    assert await provider.get_client("ghost") is None
    assert await provider.load_authorization_code(CLIENT, "anything") is None
    code = AuthorizationCode(
        code="spent",
        scopes=[],
        expires_at=0,
        client_id="ghost",
        code_challenge="c" * 43,
        redirect_uri="http://localhost/cb",
        redirect_uri_provided_explicitly=True,
    )
    with pytest.raises(TokenError) as caught:
        await provider.exchange_authorization_code(CLIENT, code)
    assert caught.value.error == "invalid_grant"


async def test_an_unknown_refresh_token_is_refused(engine: AsyncEngine) -> None:
    provider = _provider(engine)
    assert await provider.load_refresh_token(CLIENT, "nope") is None
    with pytest.raises(TokenError):
        await provider.exchange_refresh_token(CLIENT, RefreshToken(token="nope", client_id="ghost", scopes=[]), [])


async def test_a_host_without_a_name_is_registered_as_an_app(engine: AsyncEngine) -> None:
    provider = _provider(engine)
    await provider.register_client(
        OAuthClientInformationFull(client_id="nameless", redirect_uris=["http://localhost/cb"])
    )
    found = await provider.get_client("nameless")
    assert found is not None and found.client_name == "An app"


def test_a_tool_called_without_a_signed_in_member_is_refused() -> None:
    with pytest.raises(Unauthorized):
        current_principal()
