"""Which runtime a link's token is, and whether it is online.

The token is looked up by its hash before any org is known, as an install's token is. A local runtime's token stops
working when its install is signed out. A runtime is `online` from its hello and `offline` from its link's close,
`last_seen_at` stamped at both, so a call to it while it is away can say when it was last seen."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Install, Rrotor, User
from glyphh_server.ops.auth.secrets import hash_secret

ONLINE: str = "online"
OFFLINE: str = "offline"


@dataclass(frozen=True, slots=True)
class Runtime:
    id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    mode: str
    fly_machine_id: str | None = None  # hosted: the machine it is, its address's name
    public_url: str | None = None  # self-hosted: https://<host>

    def resource(self, domain: str) -> str | None:
        """Its own address's `/mcp`: the resource a Glyphh sign-in for it is bound to. A local runtime, or a hosted
        one with no machine yet, has none."""
        if self.mode == "self":
            return f"{self.public_url}/mcp"
        if self.mode == "hosted" and self.fly_machine_id:
            return f"https://{self.fly_machine_id}.{domain}/mcp"
        return None


def bearer(header: str | None) -> str | None:
    """The token of an `Authorization: Bearer <token>` header; never read from the address."""
    scheme, _, token = (header or "").partition(" ")
    return (token.strip() or None) if scheme.lower() == "bearer" else None


class Refused(Exception):
    """The link is refused: the reason is said in its close."""


async def runtime_for(engine: AsyncEngine, token: str | None) -> Runtime:
    if not token:
        raise Refused("Send the runtime's token: Authorization: Bearer <runtime token>.")
    found = (
        select(Rrotor.id, Rrotor.user_id, Rrotor.mode, User.org_id, Install.revoked_at)
        .add_columns(Rrotor.fly_machine_id, Rrotor.public_url)
        .join(User, User.id == Rrotor.user_id)
        .outerjoin(Install, Install.id == Rrotor.install_id)
        .where(Rrotor.token_hash == hash_secret(token))
    )
    async with engine.connect() as conn:
        row = (await conn.execute(found)).first()
    if row is None:
        raise Refused("This runtime token is not valid. Ask for a new one.")
    if row.mode == "local" and row.revoked_at is not None:
        raise Refused("This runtime's install was signed out. Sign in again in Claude.")
    return Runtime(row.id, row.user_id, row.org_id, row.mode, row.fly_machine_id, row.public_url)


async def mark(engine: AsyncEngine, runtime: Runtime, state: str, image_version: str | None = None) -> None:
    values: dict[str, object] = {"state": state, "last_seen_at": func.now()}
    if image_version is not None:
        values["image_version"] = image_version
    async with engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime.id).values(**values))
