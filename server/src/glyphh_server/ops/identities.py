"""Linking: a signed-in person adds Google or GitHub to their own account, so either signs them in, or takes one
away while another is left. An identity is found by the provider's own id for it, never by email, and belongs to
one person: one already another person's own account is refused, and nothing changes."""

import logging
import uuid

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Identity, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.signin import ProviderProfile, lock

log = logging.getLogger("glyphh.auth")

NAMES: dict[str, str] = {"google": "Google", "github": "GitHub"}
GONE: str = "This link is no longer valid. Start again in Claude."


async def can_link(conn: AsyncConnection, who: Principal, provider: str) -> None:
    """Refused when the person already signs in with this provider."""
    if provider in await _providers(conn, who.user_id):
        raise Conflict(f"{NAMES[provider]} is already linked to your Glyphh account.", provider=provider)


async def attach(conn: AsyncConnection, user_id: uuid.UUID, profile: ProviderProfile) -> None:
    """The identity the provider named becomes this person's, unless it is already someone else's."""
    name = NAMES[profile.provider]
    await lock(conn, f"{profile.provider}:{profile.subject}")
    owner = (
        await conn.execute(
            select(Identity.user_id).where(
                Identity.provider == profile.provider, Identity.provider_user_id == profile.subject
            )
        )
    ).scalar_one_or_none()
    if owner == user_id:
        return
    if owner is not None:
        raise Conflict(
            f"That {name} account is already its own Glyphh account, so it can't be linked to this one. To link it, "
            f"sign in to Glyphh with that {name} account and delete that account first, or contact support.",
            provider=profile.provider,
        )
    if profile.provider in await _providers(conn, user_id, locked=True):
        raise Conflict(f"Another {name} account is already linked to your Glyphh account.", provider=profile.provider)
    await conn.execute(
        insert(Identity).values(user_id=user_id, provider=profile.provider, provider_user_id=profile.subject)
    )
    log.info("identity linked", extra=fields(user=str(user_id), provider=profile.provider))


async def unlink(conn: AsyncConnection, who: Principal, provider: str) -> None:
    """Refused when it is the last way the person signs in."""
    mine = await _providers(conn, who.user_id, locked=True)
    if provider not in mine:
        raise NotFound(f"{NAMES[provider]} is not linked to your Glyphh account.", provider=provider)
    if len(mine) == 1:
        raise Conflict(
            f"{NAMES[provider]} is the only way you sign in to Glyphh. Link another provider before unlinking it.",
            provider=provider,
        )
    await conn.execute(delete(Identity).where(Identity.user_id == who.user_id, Identity.provider == provider))
    log.info("identity unlinked", extra=fields(user=str(who.user_id), provider=provider))


async def _providers(conn: AsyncConnection, user_id: uuid.UUID, locked: bool = False) -> list[str]:
    """The person's providers. Locked, the person's row is held to the end of the transaction, so two changes to
    one person's identities happen one after the other; a person who is gone is refused."""
    if locked and (await conn.execute(select(User.id).where(User.id == user_id).with_for_update())).first() is None:
        raise Invalid(GONE)
    rows = await conn.execute(select(Identity.provider).where(Identity.user_id == user_id))
    return list(rows.scalars())
