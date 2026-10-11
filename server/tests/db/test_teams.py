import uuid

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Org, Team, TeamMember, User
from tests.db.helpers import make_org, make_user


async def _team(engine: AsyncEngine, org_id: uuid.UUID, name: str) -> uuid.UUID:
    async with engine.begin() as conn:
        return (await conn.execute(insert(Team).values(org_id=org_id, name=name).returning(Team.id))).scalar_one()


async def _join(engine: AsyncEngine, org_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(insert(TeamMember).values(org_id=org_id, team_id=team_id, user_id=user_id))


async def _members(engine: AsyncEngine, team_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        query = select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team_id)
        return (await conn.execute(query)).scalar_one()


async def test_a_user_can_be_in_several_teams_once_each(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Teams Inc")
    user_id = await make_user(engine, org_id, "dev@teams.test")
    design, build = await _team(engine, org_id, "Design"), await _team(engine, org_id, "Build")
    await _join(engine, org_id, design, user_id)
    await _join(engine, org_id, build, user_id)
    with pytest.raises(IntegrityError, match="team_members_pair"):
        await _join(engine, org_id, design, user_id)


async def test_team_names_are_unique_within_an_org_only(engine: AsyncEngine) -> None:
    first, second = await make_org(engine, "Names A"), await make_org(engine, "Names B")
    await _team(engine, first, "Ops")
    await _team(engine, second, "Ops")
    with pytest.raises(IntegrityError, match="teams_name"):
        await _team(engine, first, "Ops")


async def test_a_team_only_holds_its_own_orgs_users(engine: AsyncEngine) -> None:
    home, other = await make_org(engine, "Home Org"), await make_org(engine, "Other Org")
    team_id = await _team(engine, home, "Core")
    outsider = await make_user(engine, other, "outsider@other.test")
    for org_id in (home, other):
        with pytest.raises(IntegrityError):
            await _join(engine, org_id, team_id, outsider)


async def test_memberships_go_with_their_team_or_their_user(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Cascade Co")
    team_id = await _team(engine, org_id, "Temp")
    leaving = await make_user(engine, org_id, "leaving@cascade.test")
    staying = await make_user(engine, org_id, "staying@cascade.test")
    await _join(engine, org_id, team_id, leaving)
    await _join(engine, org_id, team_id, staying)
    async with engine.begin() as conn:
        await conn.execute(delete(User).where(User.id == leaving))
    assert await _members(engine, team_id) == 1
    async with engine.begin() as conn:
        await conn.execute(delete(Team).where(Team.id == team_id))
    assert await _members(engine, team_id) == 0


async def test_caps_are_positive_or_absent(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Caps Co")
    team_id = await _team(engine, org_id, "Capped")
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == org_id).values(rpm_cap=100, tpm_cap=None))
        await conn.execute(update(Team).where(Team.id == team_id).values(rpm_cap=None, tpm_cap=10_000))
    for model, row_id, name in ((Org, org_id, "orgs_caps"), (Team, team_id, "teams_caps")):
        with pytest.raises(IntegrityError, match=name):
            async with engine.begin() as conn:
                await conn.execute(update(model).where(model.id == row_id).values(rpm_cap=0))
