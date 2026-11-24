"""The plugin's poll for its token (RFC 8628, section 3.4). Each answer before the token is returned, not raised, so
what the poll wrote (when it was polled, a slower interval) is kept."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import AccessDenied, AuthorizationPending, DeviceFlowError, ExpiredToken, SlowDown
from glyphh_server.models import DeviceCode
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.auth.secrets import hash_secret

SLOWER: int = 5


class DeviceToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    install_id: uuid.UUID


async def poll(conn: AsyncConnection, device_code: str) -> DeviceToken | DeviceFlowError:
    digest = hash_secret(device_code)
    row = (
        await conn.execute(select(DeviceCode).where(DeviceCode.device_code_hash == digest).with_for_update())
    ).first()
    if row is None:
        return ExpiredToken("This sign-in has expired. Start again in Claude.")
    code = DeviceCode(**row._mapping)
    now = datetime.now(UTC)
    ended = await _ended(conn, code, now)
    if ended is not None:
        return ended
    if code.install_id is not None:
        await conn.execute(delete(DeviceCode).where(DeviceCode.device_code_hash == digest))
        return DeviceToken(access_token=await tokens.issue(conn, code.install_id), install_id=code.install_id)
    if code.polled_at is not None and now - code.polled_at < timedelta(seconds=code.interval):
        await _polled(conn, digest, now, code.interval + SLOWER)
        return SlowDown(f"Polling too fast: wait {code.interval + SLOWER} seconds between polls.")
    await _polled(conn, digest, now, code.interval)
    return AuthorizationPending("Waiting for the person to sign in and approve.")


async def _ended(conn: AsyncConnection, code: DeviceCode, now: datetime) -> DeviceFlowError | None:
    """A denied or expired sign-in answers so once; the row goes."""
    answer: DeviceFlowError | None = None
    if code.denied_at is not None:
        answer = AccessDenied("The sign-in was denied.")
    elif code.install_id is None and code.expires_at <= now:
        answer = ExpiredToken("This sign-in has expired. Start again in Claude.")
    if answer is not None:
        await conn.execute(delete(DeviceCode).where(DeviceCode.device_code_hash == code.device_code_hash))
    return answer


async def _polled(conn: AsyncConnection, digest: str, now: datetime, interval: int) -> None:
    await conn.execute(
        update(DeviceCode).where(DeviceCode.device_code_hash == digest).values(polled_at=now, interval=interval)
    )
