"""People, orgs and installs made straight in the database, for tests that start past signing in."""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.models import Install, Org, User
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.orgs import new_person
from glyphh_server.ops.plans import newest_version


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    org_id: uuid.UUID
    install_id: uuid.UUID
    email: str
    headers: dict[str, str]


def an_email() -> str:
    return f"{uuid.uuid4().hex[:12]}@people.test"


async def _install(conn: AsyncConnection, user_id: uuid.UUID, name: str = "Mac") -> tuple[uuid.UUID, str]:
    values = {
        "user_id": user_id,
        "machine_id": uuid.uuid4().hex,
        "name": name,
        "surface": "desktop",
        "mod_version": "1.0.0",
    }
    install_id = (await conn.execute(insert(Install).values(values).returning(Install.id))).scalar_one()
    return install_id, await tokens.issue(conn, install_id)


async def _signed_in(conn: AsyncConnection, user_id: uuid.UUID, email: str) -> Person:
    org_id = (await conn.execute(select(User.org_id).where(User.id == user_id))).scalar_one()
    install_id, token = await _install(conn, user_id)
    return Person(user_id, org_id, install_id, email, {"authorization": f"Bearer {token}"})


async def person(engine: AsyncEngine, plan: str = "Free", email: str | None = None) -> Person:
    """A new person, admin of their own org on this plan's newest version, signed in on one install."""
    email = email or an_email()
    async with engine.begin() as conn:
        user_id = await new_person(conn, email, "Ada Lovelace")
        who = await _signed_in(conn, user_id, email)
        version = await newest_version(conn, plan)
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=version.id))
    return who


async def member(engine: AsyncEngine, org_id: uuid.UUID, email: str | None = None) -> Person:
    """A member of this org, signed in on one install."""
    email = email or an_email()
    async with engine.begin() as conn:
        values = {"org_id": org_id, "email": email, "name": "Grace Hopper", "role": "member"}
        user_id = (await conn.execute(insert(User).values(values).returning(User.id))).scalar_one()
        return await _signed_in(conn, user_id, email)


async def another_install(engine: AsyncEngine, user_id: uuid.UUID) -> tuple[uuid.UUID, dict[str, str]]:
    async with engine.begin() as conn:
        install_id, token = await _install(conn, user_id, "Linux box")
    return install_id, {"authorization": f"Bearer {token}"}


async def subscribed(engine: AsyncEngine, org_id: uuid.UUID, sub_id: str, customer: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            update(Org)
            .where(Org.id == org_id)
            .values(stripe_subscription_id=sub_id, stripe_customer_id=customer, billing_status="active")
        )


async def org_row(engine: AsyncEngine, org_id: uuid.UUID):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Org).where(Org.id == org_id))).one()
