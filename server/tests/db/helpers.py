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


async def make_machine(engine: AsyncEngine, org_id: uuid.UUID, user_id: uuid.UUID, name: str, online: bool = True):  # type: ignore[no-untyped-def]
    """A registered rrotor of this member's."""
    from glyphh_server.models import Machine

    values = {
        "org_id": org_id,
        "user_id": user_id,
        "name": name,
        "host": "fly",
        "platform": "linux",
        "version": "1.0.0",
        "token_hash": f"t-{uuid.uuid4()}",
        "ssh_public_key": f"k-{uuid.uuid4()}",
        "ssh_fingerprint": "SHA256:x",
        "online": online,
    }
    async with engine.begin() as conn:
        return (await conn.execute(insert(Machine).values(values).returning(Machine.id))).scalar_one()


async def install(
    engine: AsyncEngine,
    machine_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    status: str = "idle",
    minutes_ago: int | None = None,
    description: str = "",
) -> uuid.UUID:
    """A super power of this member's, installed on the machine, doing `status`, last active that long ago."""
    from datetime import UTC, datetime, timedelta

    from glyphh_server.models import SuperPower, SuperPowerInstall

    active = None if minutes_ago is None else datetime.now(UTC) - timedelta(minutes=minutes_ago)
    async with engine.begin() as conn:
        found = (
            await conn.execute(select(SuperPower.id).where(SuperPower.user_id == user_id, SuperPower.name == name))
        ).scalar()
        sp = (
            found
            or (
                await conn.execute(
                    insert(SuperPower)
                    .values(org_id=org_id, user_id=user_id, name=name, description=description)
                    .returning(SuperPower.id)
                )
            ).scalar_one()
        )
        await conn.execute(
            insert(SuperPowerInstall).values(
                super_power_id=sp, machine_id=machine_id, org_id=org_id, status=status, last_active_at=active
            )
        )
        return sp


async def make_thread(  # type: ignore[no-untyped-def]
    engine: AsyncEngine,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    machine_id: uuid.UUID,
    goal: str,
    super_power: uuid.UUID | None = None,
    crew: tuple[uuid.UUID, ...] = (),
    minutes_ago: int = 0,
    pinned: bool = False,
    archived: bool = False,
):
    """A thread of this member's on the machine: one super power's, or a crew's; last active that long ago."""
    from datetime import UTC, datetime, timedelta

    from glyphh_server.models import Thread, ThreadCrew

    at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    values = {
        "org_id": org_id,
        "user_id": user_id,
        "machine_id": machine_id,
        "goal": goal,
        "super_power_id": super_power,
        "last_event_at": at,
        "pinned_at": at if pinned else None,
        "archived_at": at if archived else None,
    }
    async with engine.begin() as conn:
        thread = (await conn.execute(insert(Thread).values(values).returning(Thread.id))).scalar_one()
        for i, sp in enumerate(crew):
            added = at - timedelta(seconds=len(crew) - i)
            await conn.execute(insert(ThreadCrew).values(thread_id=thread, super_power_id=sp, added_at=added))
        return thread


async def ask(  # type: ignore[no-untyped-def]
    engine: AsyncEngine,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    tool: str,
    super_power: uuid.UUID | None = None,
    minutes_ago: int = 0,
    answer: str | None = None,
):
    """A question a super power asked in this thread; open unless given an answer."""
    from datetime import UTC, datetime, timedelta

    from glyphh_server.models import NeedsYou

    at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    values = {
        "org_id": org_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "super_power_id": super_power,
        "ask_id": f"req-{uuid.uuid4()}",
        "tool": tool,
        "detail": f"{tool} something",
        "asked_at": at,
        "answer": answer,
        "answered_at": at if answer else None,
    }
    async with engine.begin() as conn:
        return (await conn.execute(insert(NeedsYou).values(values).returning(NeedsYou.id))).scalar_one()
