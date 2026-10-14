"""Secrets the server must read back later (a routine trigger's token) are kept encrypted with AES-256-GCM under the
server's secrets key, bound to what they belong to, so a sealed value moved to another row does not open."""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable

PREFIX: str = "v1."
NONCE_BYTES: int = 12


def load_key(settings: Settings) -> bytes | None:
    """The configured key, checked at start; none set means the features that need it answer E_UNAVAILABLE."""
    if not settings.secrets_key:
        return None
    try:
        key = base64.b64decode(settings.secrets_key, validate=True)
    except ValueError as err:
        raise RuntimeError("GLYPHH_SECRETS_KEY must be base64 of 32 random bytes.") from err
    if len(key) != 32:
        raise RuntimeError("GLYPHH_SECRETS_KEY must be base64 of 32 random bytes.")
    return key


def _cipher(key: bytes | None) -> AESGCM:
    if key is None:
        raise Unavailable("Keeping secrets isn't set up on this server.", reason="secrets_off")
    return AESGCM(key)


def seal(key: bytes | None, value: str, context: str) -> str:
    nonce = os.urandom(NONCE_BYTES)
    sealed = _cipher(key).encrypt(nonce, value.encode(), context.encode())
    return PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode()


def unseal(key: bytes | None, sealed: str, context: str) -> str:
    """The value back. A value that does not open (another key, another row) is the server's own fault: a crash."""
    cipher = _cipher(key)
    raw = base64.urlsafe_b64decode(sealed.removeprefix(PREFIX))
    try:
        return cipher.decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], context.encode()).decode()
    except InvalidTag as err:
        raise RuntimeError("A sealed secret did not open: the secrets key changed, or the value was moved.") from err
