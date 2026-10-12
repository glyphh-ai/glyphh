import uuid

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Membership, OAuthClient, Org, Plan, User


async def plan_id(engine: AsyncEngine, name: str = "Free") -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Plan.id).where(Plan.name == name))).scalar_one()


async def parent_id(engine: AsyncEngine) -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Org.id).where(Org.parent_id.is_(None)))).scalar_one()


async def make_org(engine: AsyncEngine, name: str, plan: str = "Enterprise") -> uuid.UUID:
    """An org; on Enterprise (no seat limit) unless a test is about a plan."""
    values = {"name": name, "parent_id": await parent_id(engine), "plan_id": await plan_id(engine, plan)}
    async with engine.begin() as conn:
        return (await conn.execute(insert(Org).values(values).returning(Org.id))).scalar_one()


async def make_user(engine: AsyncEngine, org_id: uuid.UUID, email: str, role: str = "user") -> uuid.UUID:
    """A person, a member of this org with this role."""
    values = {"email": email, "first_name": "Ada", "last_name": "Lovelace"}
    async with engine.begin() as conn:
        user = (await conn.execute(insert(User).values(values).returning(User.id))).scalar_one()
        await conn.execute(insert(Membership).values(user_id=user, org_id=org_id, role=role))
        return user


async def make_client(engine: AsyncEngine, client_id: str = "claude-code") -> uuid.UUID:
    values = {"client_id": client_id, "name": "Claude Code", "redirect_uris": ["http://localhost:33418/callback"]}
    async with engine.begin() as conn:
        return (await conn.execute(insert(OAuthClient).values(values).returning(OAuthClient.id))).scalar_one()


async def bearer(engine: AsyncEngine, email: str) -> str:
    """A member of a new org, signed in: the Authorization header value for their access token."""
    from glyphh_server.ops.auth import tokens

    org = await make_org(engine, f"Org of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        return "Bearer " + (await tokens.issue(conn, user, org)).access_token


async def make_plan(engine: AsyncEngine, name: str, seats: int | None) -> uuid.UUID:
    values = {"name": name, "price_cents": 0, "max_seats": seats}
    async with engine.begin() as conn:
        return (await conn.execute(insert(Plan).values(values).returning(Plan.id))).scalar_one()


async def admin_of(engine: AsyncEngine, org_name: str, plan: str = "Enterprise"):
    """A new org and its org admin, as the principal operations run as."""
    from glyphh_server.ops.auth.principal import Principal

    org = await make_org(engine, org_name, plan)
    user = await make_user(engine, org, f"admin@{uuid.uuid4().hex[:8]}.test", "org_admin")
    return Principal(user_id=user, org_id=org, role="org_admin")
