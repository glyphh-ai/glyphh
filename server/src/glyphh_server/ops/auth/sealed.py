"""A secret kept at rest (an org's OpenID Connect client secret): AES-256-GCM under a key derived from the server's
secret key, so the database alone gives nothing away. `v1.` then base64url of the nonce and the ciphertext; a value
sealed under another key, or changed, does not open (InvalidTag)."""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PREFIX: str = "v1."
NONCE: int = 12


def _key(secret: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"glyphh sealed v1").derive(secret.encode())


def seal(secret: str, value: str) -> str:
    nonce = os.urandom(NONCE)
    sealed = nonce + AESGCM(_key(secret)).encrypt(nonce, value.encode(), None)
    return PREFIX + base64.urlsafe_b64encode(sealed).decode().rstrip("=")


def unseal(secret: str, sealed: str) -> str:
    """The value back; ValueError when it is not a sealed value, InvalidTag when it was sealed under another key."""
    if not sealed.startswith(PREFIX):
        raise ValueError("not a sealed value")
    body = sealed[len(PREFIX) :]
    raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    return AESGCM(_key(secret)).decrypt(raw[:NONCE], raw[NONCE:], None).decode()
