"""A secret sealed at rest opens only under the key it was sealed with, and never as anything else."""

import pytest
from cryptography.exceptions import InvalidTag

from glyphh_server.ops.auth.sealed import seal, unseal

KEY: str = "test-secret-key-that-signs-sign-in-links-0123456789"


def test_a_sealed_value_opens_under_its_key_and_is_never_the_same_twice() -> None:
    one, two = seal(KEY, "s3cret"), seal(KEY, "s3cret")
    assert one != two and one.startswith("v1.") and "s3cret" not in one
    assert unseal(KEY, one) == unseal(KEY, two) == "s3cret"


def test_another_key_a_change_or_a_plain_value_does_not_open() -> None:
    sealed = seal(KEY, "s3cret")
    with pytest.raises(InvalidTag):
        unseal("another-key-of-the-right-length-0123456789abcdef", sealed)
    with pytest.raises(InvalidTag):
        unseal(KEY, sealed[:-2] + ("AA" if not sealed.endswith("AA") else "BB"))
    with pytest.raises(ValueError, match="not a sealed value"):
        unseal(KEY, "s3cret")
