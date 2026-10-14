import pytest

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from tests.conftest import SECRET_KEY


def test_the_server_refuses_to_start_without_a_secret_key() -> None:
    with pytest.raises(RuntimeError, match="GLYPHH_SECRET_KEY"):
        create_app(Settings(secret_key="short"))


def test_the_server_refuses_to_start_in_prod_without_a_license_key() -> None:
    with pytest.raises(RuntimeError, match="GLYPHH_LICENSE_KEY"):
        create_app(Settings(secret_key=SECRET_KEY, env="prod"))


def test_the_invite_link_defaults_to_the_public_address() -> None:
    assert Settings(public_url="https://api.glyphh.ai/").invite_base == "https://api.glyphh.ai/join"
    assert Settings(invite_url="https://glyphh.ai/join/").invite_base == "https://glyphh.ai/join"
