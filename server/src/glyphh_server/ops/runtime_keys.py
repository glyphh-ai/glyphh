"""What Ada Cloud's API keys (glyphh_ada/keys.py, kept in runtime_keys) share: a key is kept as its SHA-256, and
expires 1 to 365 days after it is made, or never."""

import hashlib
from datetime import UTC, datetime, timedelta

from glyphh_server.errors import Invalid

MAX_DAYS: int = 365


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def expiry(days: int | None) -> datetime | None:
    """When a key made now for `days` expires; None never does. Past a year is refused."""
    if days is None:
        return None
    if not 1 <= days <= MAX_DAYS:
        raise Invalid("An API key lasts 1 to 365 days, or never expires.", reason="expiry_range", days=days)
    return datetime.now(UTC) + timedelta(days=days)
