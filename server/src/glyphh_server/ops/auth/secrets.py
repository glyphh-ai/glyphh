"""Secrets the server hands out (tokens, codes) are random and kept only as hashes."""

import hashlib
import secrets


def make_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    """A secret is 256 random bits, so one SHA-256 is enough: there is nothing to guess."""
    return hashlib.sha256(secret.encode()).hexdigest()
