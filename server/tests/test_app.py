import pytest
from fastapi import FastAPI

from glyphh_server.app import ROUTERS, create_app
from glyphh_server.config import Settings
from tests.conftest import PUBLIC_URL, SECRET_KEY, SETTINGS


def test_the_server_refuses_to_start_without_a_secret_key() -> None:
    for short in ("", "short", "x" * 31):
        with pytest.raises(RuntimeError, match="GLYPHH_SECRET_KEY"):
            create_app(Settings(secret_key=short))


def test_the_server_starts_in_prod_with_only_its_secret_key() -> None:
    app = create_app(Settings(secret_key=SECRET_KEY, env="prod", version="1.2.3"))
    assert isinstance(app, FastAPI) and app.version == "1.2.3"
    assert app.state.settings.env == "prod"


def test_the_app_has_only_the_routes_that_are_left() -> None:
    """The spec is served nowhere any more (api/gone.py), but it still lists what the server answers: every route
    has an operation id, and the token is a bearer. The browser's steps of the sign-in are left out of it."""
    spec = create_app(SETTINGS).openapi()
    ops = {(m.upper(), p): o.get("operationId") for p, v in spec["paths"].items() for m, o in v.items()}
    assert len(ROUTERS) == 7 and all(ops.values()) and len(set(ops.values())) == len(ops)
    assert {route: op for route, op in ops.items() if not route[1].startswith("/v1/admin/")} == {
        ("GET", "/v1/health"): "health",
        ("POST", "/v1/stripe/webhook"): "stripeWebhook",
        ("GET", "/v1/me"): "me",
        ("GET", "/oauth/authorize"): "oauthAuthorize",
        ("POST", "/oauth/token"): "oauthToken",
        ("POST", "/oauth/revoke"): "oauthRevoke",
        ("GET", "/auth/providers"): "signInProviders",
    }
    assert all(op.startswith("admin") for route, op in ops.items() if route[1].startswith("/v1/admin/"))
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert spec["paths"]["/v1/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in spec["paths"]["/v1/health"]["get"]


def test_the_settings_of_the_retired_products_are_gone() -> None:
    fields = set(Settings.model_fields)
    for gone in ("products", "rrotor", "ada_cloud", "llm", "license_signing_key", "mcp_origins", "invite_url"):
        assert gone not in fields, gone
    assert not [f for f in fields if f.startswith(("ada_", "inference_", "github_app_", "github_traffic_", "stripe_p"))]
    assert Settings(products=True, secret_key=SECRET_KEY).secret_key == SECRET_KEY  # type: ignore[call-arg]  # an old one set: ignored


def test_only_support_is_staff_unless_told_otherwise() -> None:
    assert Settings(_env_file=None).staff_set == {"support@glyphh.ai"}  # type: ignore[call-arg]
    assert Settings(staff_emails=" A@glyphh.test, ,b@glyphh.test,").staff_set == {"a@glyphh.test", "b@glyphh.test"}
    assert Settings(staff_emails="").staff_set == frozenset()


def test_the_servers_addresses_have_no_trailing_slash_and_tokens_keep_their_resource() -> None:
    cfg = Settings(public_url="https://api.glyphh.ai/", platform_url="https://platform.glyphh.ai/")
    assert (cfg.base_url, cfg.platform_base) == ("https://api.glyphh.ai", "https://platform.glyphh.ai")
    assert cfg.token_resource == "https://api.glyphh.ai/mcp"
    assert SETTINGS.token_resource == f"{PUBLIC_URL}/mcp"


def test_a_plain_postgres_url_is_made_the_asyncpg_drivers() -> None:
    assert Settings(database_url="postgres://u:p@h:5432/d?sslmode=disable").database_url == (
        "postgresql+asyncpg://u:p@h:5432/d?ssl=disable"
    )
    assert Settings(database_url="postgresql://u:p@h/d?a=1&sslmode=require").database_url == (
        "postgresql+asyncpg://u:p@h/d?a=1&ssl=require"
    )
    asyncpg = "postgresql+asyncpg://u:p@h/d"
    assert Settings(database_url=asyncpg).database_url == asyncpg
