"""Self-hosted runtimes: a rrotor the person runs on their own infrastructure (Docker Compose, a Helm chart,
Terraform), registered here by name and the public address it answers at, `https://<host>`. Its token is shown once
and kept only as a hash; rotating it, or deleting the runtime, closes its link. It links like any rrotor, but nothing
here runs it: it is never provisioned, woken or stopped, and never tallied. Its licence comes in
its welcome, from its daily heartbeat, or, air-gapped, as an offline licence (ops/heartbeat.py)."""

import re
import uuid
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.runtimes import NOT_LINKED

LABEL: str = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOST: re.Pattern[str] = re.compile(rf"^(?=.{{1,253}}$){LABEL}(?:\.{LABEL})*$")
ADDRESS_RULE: str = "The public address is https://<host>: the exact host it answers at, with no port, path or query."


class SelfRuntime(BaseModel):
    id: uuid.UUID
    name: str
    public_url: str = Field(description="https://<host>; its /mcp is where Claude reaches it")
    state: str = Field(description="stopped until it first links, then online or offline")
    version: str | None = Field(description="The rrotor version it last said, linking or in its heartbeat")
    last_seen_at: datetime | None
    last_heartbeat_at: datetime | None


class MadeSelf(BaseModel):
    id: uuid.UUID
    name: str
    public_url: str
    token: str = Field(description="The runtime's token: shown once, never stored")
    env: dict[str, str] = Field(description="Its environment, filled in: RROTOR_MODE, _SERVER, _RUNTIME_ID, ...")


class Token(BaseModel):
    token: str = Field(description="The runtime's new token: shown once, never stored")


def _host_of(url: str) -> str | None:
    return urlsplit(url).hostname


def public_address(settings: Settings, asked: str) -> str:
    """The address as kept, `https://<host>` lowercased; anything else is refused, and so is an address of Glyphh's
    own (a hosted runtime's domain, the server, the platform)."""
    raw = asked.strip()
    parts = urlsplit(raw)
    host = parts.hostname or ""
    plain = parts.scheme.lower() == "https" and parts.netloc.lower() == host and parts.path in ("", "/")
    if not plain or "?" in raw or "#" in raw or not HOST.match(host):
        raise Invalid(ADDRESS_RULE, reason="public_url")
    domain = settings.fly_public_domain.lower()
    if (
        host == domain
        or host.endswith(f".{domain}")
        or host in (_host_of(settings.base_url), _host_of(settings.platform_base))
    ):
        raise Invalid("That address is one of Glyphh's own.", reason="public_url")
    return f"https://{host}"


def self_env(settings: Settings, runtime_id: uuid.UUID, token: str, public_url: str) -> dict[str, str]:
    """What the self-hosted rrotor needs: where Glyphh is, who it is, its token and the host it answers at."""
    return {
        "RROTOR_MODE": "self",
        "RROTOR_SERVER": settings.base_url,
        "RROTOR_RUNTIME_ID": str(runtime_id),
        "RROTOR_RUNTIME_TOKEN": token,
        "RROTOR_PUBLIC_HOST": public_url.removeprefix("https://"),
    }


async def register(conn: AsyncConnection, settings: Settings, who: Principal, name: str, asked: str) -> MadeSelf:
    url = public_address(settings, asked)
    mine = select(Rrotor.id).where(Rrotor.user_id == who.user_id, Rrotor.mode == "self", Rrotor.public_url == url)
    if (await conn.execute(mine)).first() is not None:
        raise Conflict("You have a self-hosted runtime at that address already.", reason="registered", public_url=url)
    token = make_secret()
    values = {"user_id": who.user_id, "mode": "self", "name": name, "public_url": url, "state": NOT_LINKED}
    made = insert(Rrotor).values(**values, token_hash=hash_secret(token)).returning(Rrotor.id)
    runtime_id = (await conn.execute(made)).scalar_one()
    return MadeSelf(
        id=runtime_id, name=name, public_url=url, token=token, env=self_env(settings, runtime_id, token, url)
    )


async def list_self(conn: AsyncConnection, who: Principal) -> list[SelfRuntime]:
    found = (
        select(Rrotor.id, Rrotor.name, Rrotor.public_url, Rrotor.state, Rrotor.image_version.label("version"))
        .add_columns(Rrotor.last_seen_at, Rrotor.last_heartbeat_at)
        .where(Rrotor.user_id == who.user_id, Rrotor.mode == "self")
        .order_by(Rrotor.name, Rrotor.id)
    )
    return [SelfRuntime.model_validate(r._mapping) for r in await conn.execute(found)]


async def mine(conn: AsyncConnection, who: Principal, runtime_id: uuid.UUID) -> uuid.UUID:
    found = select(Rrotor.id).where(Rrotor.id == runtime_id, Rrotor.user_id == who.user_id, Rrotor.mode == "self")
    if (await conn.execute(found)).first() is None:
        raise NotFound("You have no such self-hosted runtime.", runtime_id=str(runtime_id))
    return runtime_id


async def rotate(conn: AsyncConnection, hub: Hub, who: Principal, runtime_id: uuid.UUID) -> Token:
    """A new token, shown once; the old one stops at once, its link closed. The link's sequence numbers start
    again, as a local runtime's do."""
    await mine(conn, who, runtime_id)
    token = make_secret()
    await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(token_hash=hash_secret(token), seq=0))
    await hub.drop(runtime_id, "This runtime's token was replaced. Use the new one.")
    return Token(token=token)


async def delete_self(conn: AsyncConnection, hub: Hub, who: Principal, runtime_id: uuid.UUID) -> None:
    """The record goes, with its keys, deployments and runs; what is on the runtime's own volume stays there."""
    await mine(conn, who, runtime_id)
    await conn.execute(delete(Rrotor).where(Rrotor.id == runtime_id))
    await hub.drop(runtime_id, "This runtime was deleted from Glyphh.")
