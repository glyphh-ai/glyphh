"""The record of programs: a hosted runtime per user, programs and their versions, deployments, runs and approvals,
and connector grants, each seen only by its own org."""

import uuid

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import (
    Approval,
    ConnectorGrant,
    Deployment,
    Program,
    ProgramVersion,
    Rrotor,
    Run,
)
from tests.db.helpers import Person, person

TABLES = (Rrotor, Program, ProgramVersion, Deployment, Run, Approval, ConnectorGrant)


async def _new(conn: AsyncConnection, table: type, **values: object) -> uuid.UUID:
    return (await conn.execute(insert(table).values(**values).returning(table.id))).scalar_one()


def _rrotor(who: Person) -> dict[str, object]:
    return {"user_id": who.user_id, "region": "iad", "image_version": "1", "state": "stopped", "token_hash": who.email}


async def _programs_of(engine: AsyncEngine, who: Person) -> None:
    async with engine.begin() as conn:
        rrotor_id = await _new(conn, Rrotor, **_rrotor(who))
        program_id = await _new(conn, Program, user_id=who.user_id, org_id=who.org_id, name="leads")
        version_id = await _new(
            conn, ProgramVersion, program_id=program_id, version=1, manifest={"functions": []}, bundle_ref="b/1"
        )
        await conn.execute(insert(Deployment).values(rrotor_id=rrotor_id, program_version_id=version_id))
        values = {"program_version_id": version_id, "rrotor_id": rrotor_id, "function": "start", "status": "done"}
        run_id = await _new(conn, Run, **values, caller="routine")
        await _new(conn, Approval, run_id=run_id, step="post", prompt="Post it?")
        await _new(conn, ConnectorGrant, user_id=who.user_id, client="claude.ai", token_hash=f"g-{who.email}")


async def test_a_tenant_sees_only_its_own_programs_and_runs(engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    for who in (ada, eve):
        await _programs_of(engine, who)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        for table in TABLES:
            assert (await conn.execute(select(func.count()).select_from(table))).scalar_one() == 1, table
        assert (await conn.execute(select(Deployment.active))).scalar_one() is True
        assert (await conn.execute(select(Run.ended_at, Run.seconds))).one() == (None, None)


async def test_one_hosted_runtime_per_user_and_only_known_callers(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    await _programs_of(engine, ada)
    with pytest.raises(IntegrityError, match="rrotors_user_id_key"):
        async with engine.begin() as conn:
            await conn.execute(insert(Rrotor).values(**_rrotor(ada) | {"token_hash": "another"}))
    with pytest.raises(IntegrityError, match="runs_caller"):
        async with engine.begin() as conn:
            run = (await conn.execute(select(Run).join(Rrotor).where(Rrotor.user_id == ada.user_id))).one()
            values = {"program_version_id": run.program_version_id, "rrotor_id": run.rrotor_id}
            await conn.execute(insert(Run).values(**values, function="start", status="done", caller="cron"))
