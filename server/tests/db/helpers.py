import uuid

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient, Org, Plan, User


async def plan_id(engine: AsyncEngine, name: str = "Free") -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Plan.id).where(Plan.name == name))).scalar_one()


async def parent_id(engine: AsyncEngine) -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Org.id).where(Org.parent_id.is_(None)))).scalar_one()


async def make_org(engine: AsyncEngine, name: str, plan: str = "Free") -> uuid.UUID:
    values = {"name": name, "parent_id": await parent_id(engine), "plan_id": await plan_id(engine, plan)}
    async with engine.begin() as conn:
        return (await conn.execute(insert(Org).values(values).returning(Org.id))).scalar_one()


async def make_user(engine: AsyncEngine, org_id: uuid.UUID, email: str, role: str = "user") -> uuid.UUID:
    values = {"org_id": org_id, "role": role, "email": email, "first_name": "Ada", "last_name": "Lovelace"}
    async with engine.begin() as conn:
        return (await conn.execute(insert(User).values(values).returning(User.id))).scalar_one()


async def make_client(engine: AsyncEngine, client_id: str = "claude-code") -> uuid.UUID:
    values = {"client_id": client_id, "name": "Claude Code", "redirect_uris": ["http://localhost:33418/callback"]}
    async with engine.begin() as conn:
        return (await conn.execute(insert(OAuthClient).values(values).returning(OAuthClient.id))).scalar_one()
