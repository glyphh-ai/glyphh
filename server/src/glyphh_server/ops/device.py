"""Signing an install in by device flow (RFC 8628). The mod asks for a code; the person opens the link, signs in
and approves; the mod, polling, gets the install's token, once. Each approval is an install, refused past the
plan's max_installs."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import DeviceCode
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

CODE_TTL: timedelta = timedelta(minutes=10)
INTERVAL: int = 5
# No vowels, so a code never spells a word; 20^8 codes.
ALPHABET: str = "BCDFGHJKLMNPQRSTVWXZ"

Surface = Literal["desktop", "cli"]


class DeviceStart(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    interval: int
    expires_in: int


def new_user_code() -> str:
    letters = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{letters[:4]}-{letters[4:]}"


def normalize(code: str) -> str:
    letters = "".join(c for c in code.upper() if c.isalpha())
    return f"{letters[:4]}-{letters[4:]}"


async def start(
    conn: AsyncConnection, settings: Settings, name: str, surface: Surface, mod_version: str
) -> DeviceStart:
    await conn.execute(delete(DeviceCode).where(DeviceCode.expires_at < datetime.now(UTC) - CODE_TTL))
    device_code, user_code = make_secret(), new_user_code()
    await conn.execute(
        insert(DeviceCode).values(
            device_code_hash=hash_secret(device_code),
            user_code=user_code,
            name=name,
            surface=surface,
            mod_version=mod_version,
            interval=INTERVAL,
            expires_at=datetime.now(UTC) + CODE_TTL,
        )
    )
    page = f"{settings.base_url}/v1/device"
    return DeviceStart(
        device_code=device_code,
        user_code=user_code,
        verification_uri=page,
        verification_uri_complete=f"{page}?{urlencode({'code': user_code})}",
        interval=INTERVAL,
        expires_in=int(CODE_TTL.total_seconds()),
    )
