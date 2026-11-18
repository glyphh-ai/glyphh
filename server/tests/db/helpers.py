"""People and orgs made straight in the database, for tests that start past signing in: each person holds an access
token of the platform's own OAuth client, as the platform does after its sign-in."""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.models import OAuthClient, Org, Plan, PlanVersion, User
from glyphh_server.ops.connector import grants, tokens
from glyphh_server.ops.orgs import new_person
from tests.conftest import PLATFORM_ID, PUBLIC_URL

RESOURCE: str = f"{PUBLIC_URL}/mcp"  # what every token is bound to (config.py, token_resource)


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    org_id: uuid.UUID
    grant_id: uuid.UUID
    email: str
    headers: dict[str, str]


def an_email() -> str:
    return f"{uuid.uuid4().hex[:12]}@people.test"


async def _granted(conn: AsyncConnection, user_id: uuid.UUID, client_id: uuid.UUID, resource: str) -> tuple:  # type: ignore[type-arg]
    grant_id = await grants.grant_for(conn, user_id, client_id, "account", resource)
    answer = await tokens.issue(conn, grant_id, "account")
    return grant_id, {"authorization": f"Bearer {answer.access_token}"}


async def _signed_in(conn: AsyncConnection, user_id: uuid.UUID, email: str) -> Person:
    org_id = (await conn.execute(select(User.org_id).where(User.id == user_id))).scalar_one()
    grant_id, headers = await _granted(conn, user_id, PLATFORM_ID, RESOURCE)
    return Person(user_id, org_id, grant_id, email, headers)


async def plan_version(conn: AsyncConnection, plan: str) -> uuid.UUID:
    """A plan's newest version."""
    newest = select(PlanVersion.id).join(Plan, Plan.id == PlanVersion.plan_id).where(Plan.name == plan)
    return (await conn.execute(newest.order_by(PlanVersion.version.desc()).limit(1))).scalar_one()


async def person(engine: AsyncEngine, plan: str = "Free", email: str | None = None) -> Person:
    """A new person, admin of their own org on this plan's newest version, signed in through the platform."""
    email = email or an_email()
    async with engine.begin() as conn:
        user_id = await new_person(conn, email, "Ada Lovelace")
        who = await _signed_in(conn, user_id, email)
        await conn.execute(
            update(Org).where(Org.id == who.org_id).values(plan_version_id=await plan_version(conn, plan))
        )
    return who


async def member(engine: AsyncEngine, org_id: uuid.UUID, email: str | None = None) -> Person:
    """A member of this org, signed in through the platform."""
    email = email or an_email()
    async with engine.begin() as conn:
        values = {"org_id": org_id, "email": email, "name": "Grace Hopper", "role": "member"}
        user_id = (await conn.execute(insert(User).values(values).returning(User.id))).scalar_one()
        return await _signed_in(conn, user_id, email)


async def other_client(engine: AsyncEngine, name: str = "Claude") -> uuid.UUID:
    """An OAuth client that is not the platform's: one the retired connector left in the database."""
    values = {"name": name, "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "auth_method": "none"}
    values |= {"grant_types": ["authorization_code", "refresh_token"]}
    async with engine.begin() as conn:
        return (await conn.execute(insert(OAuthClient).values(values).returning(OAuthClient.id))).scalar_one()


async def granted(
    engine: AsyncEngine, who: Person, resource: str = RESOURCE, client_id: uuid.UUID = PLATFORM_ID
) -> tuple[uuid.UUID, dict[str, str]]:
    """A grant made straight in the database, the platform's unless another client is given: its id, and the
    Authorization header of an access token it holds."""
    async with engine.begin() as conn:
        return await _granted(conn, who.user_id, client_id, resource)


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
