"""Secrets the server reads back: sealed under its key, bound to what they belong to."""

import base64
import os

import pytest

from glyphh_server.errors import Unavailable
from glyphh_server.ops import vault
from tests.conftest import SETTINGS


def test_the_key_is_checked_at_start() -> None:
    assert vault.load_key(SETTINGS.model_copy(update={"secrets_key": ""})) is None
    assert len(vault.load_key(SETTINGS) or b"") == 32
    for bad in ("not base64!", base64.b64encode(os.urandom(16)).decode()):
        with pytest.raises(RuntimeError, match="GLYPHH_SECRETS_KEY"):
            vault.load_key(SETTINGS.model_copy(update={"secrets_key": bad}))


def test_a_sealed_value_opens_only_with_its_key_and_its_context() -> None:
    key = vault.load_key(SETTINGS)
    sealed = vault.seal(key, "the token", "trigger:a")
    assert (
        sealed.startswith("v1.") and "the token" not in sealed and sealed != vault.seal(key, "the token", "trigger:a")
    )
    assert vault.unseal(key, sealed, "trigger:a") == "the token"
    for other_key, context in ((key, "trigger:b"), (os.urandom(32), "trigger:a")):
        with pytest.raises(RuntimeError, match="did not open"):
            vault.unseal(other_key, sealed, context)
    for call in (lambda: vault.seal(None, "x", "c"), lambda: vault.unseal(None, sealed, "c")):
        with pytest.raises(Unavailable):
            call()
