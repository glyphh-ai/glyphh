"""The record of models: runtimes (one hosted per user, one local per install), models and their versions (a
commit each), deployments, runs and approvals, GitHub installations, routine triggers and model events, each seen
only by its own org."""

import uuid

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import (
    Approval,
    Deployment,
    GitHubInstallation,
    Model,
    ModelEvent,
    ModelVersion,
    RoutineTrigger,
    Rrotor,
    Run,
)
from tests.db.helpers import Person, another_install, person

TABLES = (
    Rrotor,
    Model,
    ModelVersion,
    Deployment,
    Run,
    Approval,
    GitHubInstallation,
    RoutineTrigger,
    ModelEvent,
)
SHA: str = "0123456789abcdef0123456789abcdef01234567"


async def _new(conn: AsyncConnection, table: type, **values: object) -> uuid.UUID:
    return (await conn.execute(insert(table).values(**values).returning(table.id))).scalar_one()


def _hosted(who: Person) -> dict[str, object]:
    return {
        "user_id": who.user_id,
        "mode": "hosted",
        "region": "iad",
        "image_version": "1",
        "state": "stopped",
        "token_hash": who.email,
    }


def _local(who: Person, install_id: uuid.UUID) -> dict[str, object]:
    values = {"user_id": who.user_id, "mode": "local", "install_id": install_id, "state": "stopped"}
    return values | {"token_hash": f"{install_id}-{uuid.uuid4()}"}


async def _models_of(engine: AsyncEngine, who: Person) -> None:
    async with engine.begin() as conn:
        rrotor_id = await _new(conn, Rrotor, **_hosted(who))
        model_id = await _new(conn, Model, user_id=who.user_id, org_id=who.org_id, name="leads", repo="o/leads")
        values = {"model_id": model_id, "version": 1, "commit_sha": SHA, "manifest": {"functions": []}}
        version_id = await _new(conn, ModelVersion, **values)
        await conn.execute(insert(Deployment).values(rrotor_id=rrotor_id, model_version_id=version_id))
        values = {"model_version_id": version_id, "rrotor_id": rrotor_id, "function": "start", "status": "done"}
        run_id = await _new(conn, Run, **values, caller="routine")
        await _new(conn, Approval, run_id=run_id, step="post", prompt="Post it?")
        gh = {"user_id": who.user_id, "installation_id": uuid.uuid4().int % 10**12, "account_login": "octo"}
        await _new(conn, GitHubInstallation, **gh)
        trigger = {"user_id": who.user_id, "model_id": model_id, "name": "Sales", "fire_url": "u", "token_enc": "e"}
        trigger_id = await _new(conn, RoutineTrigger, **trigger)
        await _new(conn, ModelEvent, model_id=model_id, routine_trigger_id=trigger_id, kind="done")


async def test_a_tenant_sees_only_its_own_models_and_runs(engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    for who in (ada, eve):
        await _models_of(engine, who)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        for table in TABLES:
            assert (await conn.execute(select(func.count()).select_from(table))).scalar_one() == 1, table
        assert (await conn.execute(select(Deployment.active))).scalar_one() is True
        assert (await conn.execute(select(Run.ended_at, Run.seconds))).one() == (None, None)
        assert (await conn.execute(select(Approval.notified_at))).scalar_one() is None
        assert (await conn.execute(select(RoutineTrigger.status))).scalar_one() == "ok"


async def _refused(engine: AsyncEngine, constraint: str, table: type, **values: object) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        async with engine.begin() as conn:
            await conn.execute(insert(table).values(**values))


async def test_one_hosted_runtime_per_user_and_one_local_per_install(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    await _models_of(engine, ada)
    await _refused(engine, "rrotors_one_hosted", Rrotor, **_hosted(ada) | {"token_hash": "another"})
    await _refused(engine, "rrotors_local_install", Rrotor, **_hosted(ada) | {"install_id": ada.install_id})
    await _refused(engine, "rrotors_local_install", Rrotor, **_local(ada, ada.install_id) | {"install_id": None})
    await _refused(engine, "rrotors_mode", Rrotor, **_hosted(ada) | {"mode": "cloud", "token_hash": "cloud"})
    linux, _ = await another_install(engine, ada.user_id)
    async with engine.begin() as conn:
        await conn.execute(insert(Rrotor).values(**_local(ada, ada.install_id)))
        await conn.execute(insert(Rrotor).values(**_local(ada, linux)))
    await _refused(engine, "rrotors_install_id_key", Rrotor, **_local(ada, ada.install_id))


async def test_a_commit_is_one_version_and_only_known_values_are_kept(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    await _models_of(engine, ada)
    async with engine.connect() as conn:
        version = (await conn.execute(select(ModelVersion).join(Model).where(Model.user_id == ada.user_id))).one()
        run = (await conn.execute(select(Run).where(Run.model_version_id == version.id))).one()
        trigger = (await conn.execute(select(RoutineTrigger).where(RoutineTrigger.user_id == ada.user_id))).one()
    same = {"model_id": version.model_id, "version": 2, "commit_sha": SHA, "manifest": {}}
    await _refused(engine, "model_versions_commit", ModelVersion, **same)
    values = {"model_version_id": run.model_version_id, "rrotor_id": run.rrotor_id}
    await _refused(engine, "runs_caller", Run, **values, function="start", status="done", caller="cron")
    await _refused(
        engine,
        "routine_triggers_status",
        RoutineTrigger,
        user_id=ada.user_id,
        name="x",
        fire_url="u",
        token_enc="e",
        status="lost",
    )
    gh = {"user_id": ada.user_id, "installation_id": 1, "account_login": "octo"}
    await _refused(engine, "github_installations_user_id_key", GitHubInstallation, **gh)
    assert trigger.model_id == version.model_id
