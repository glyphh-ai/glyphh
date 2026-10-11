import pytest

from glyphh_server.app import create_app
from glyphh_server.config import Settings


def test_the_server_refuses_to_start_without_a_secret_key() -> None:
    with pytest.raises(RuntimeError, match="GLYPHH_SECRET_KEY"):
        create_app(Settings(secret_key="short"))
