import pytest

from glyphh_server.app import create_app
from glyphh_server.config import Settings


def test_the_server_refuses_to_start_without_a_secret_key() -> None:
    with pytest.raises(RuntimeError, match="GLYPHH_SECRET_KEY"):
        create_app(Settings(secret_key="short"))


def test_the_invite_link_defaults_to_the_public_address() -> None:
    assert Settings(public_url="https://api.glyphh.ai/").invite_base == "https://api.glyphh.ai/join"
    assert Settings(invite_url="https://glyphh.ai/join/").invite_base == "https://glyphh.ai/join"


def test_a_plain_postgres_url_is_made_the_asyncpg_drivers() -> None:
    assert Settings(database_url="postgres://u:p@h:5432/d?sslmode=disable").database_url == (
        "postgresql+asyncpg://u:p@h:5432/d?ssl=disable"
    )
    assert Settings(database_url="postgresql://u:p@h/d?a=1&sslmode=require").database_url == (
        "postgresql+asyncpg://u:p@h/d?a=1&ssl=require"
    )
    asyncpg = "postgresql+asyncpg://u:p@h/d"
    assert Settings(database_url=asyncpg).database_url == asyncpg
