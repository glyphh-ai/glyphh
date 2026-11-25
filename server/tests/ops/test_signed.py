import time

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.signed import sign, verify

KEY: str = "k" * 40


def test_a_signed_value_comes_back_as_it_went_in() -> None:
    body = verify(KEY, sign(KEY, {"client_id": "codex", "n": 1}, 60))
    assert body["client_id"] == "codex" and body["n"] == 1 and body["exp"] > time.time()


@pytest.mark.parametrize("token", ["", "no-dot", "abc.def", "e30.0000"])
def test_garbage_is_refused(token: str) -> None:
    with pytest.raises(Invalid, match="not valid"):
        verify(KEY, token)


def test_a_value_signed_with_another_key_or_changed_is_refused() -> None:
    token = sign(KEY, {"client_id": "codex"}, 60)
    with pytest.raises(Invalid, match="not valid"):
        verify("x" * 40, token)
    raw, mac = token.split(".")
    with pytest.raises(Invalid, match="not valid"):
        verify(KEY, raw[:-2] + "AA." + mac)


def test_an_expired_value_is_refused() -> None:
    with pytest.raises(Invalid, match="expired"):
        verify(KEY, sign(KEY, {}, -1))
