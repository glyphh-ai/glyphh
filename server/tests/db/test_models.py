"""The record of runtimes (one local per install, self-hosted ones at their own address) and GitHub installations,
each seen only by its own org."""

import uuid

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import GitHubInstallation, Rrotor
from tests.db.helpers import Person, another_install, person

TABLES = (Rrotor, GitHubInstallation)


async def _new(conn: AsyncConnection, table: type, **values: object) -> uuid.UUID:
    return (await conn.execute(insert(table).values(**values).returning(table.id))).scalar_one()


def _self(who: Person) -> dict[str, object]:
    return {
        "user_id": who.user_id,
        "mode": "self",
        "name": "Acme",
        "public_url": f"https://{who.user_id.hex}.acme.test",
        "image_version": "1",
        "state": "stopped",
        "token_hash": who.email,
    }


def _local(who: Person, install_id: uuid.UUID) -> dict[str, object]:
    values = {"user_id": who.user_id, "mode": "local", "install_id": install_id, "state": "stopped"}
    return values | {"token_hash": f"{install_id}-{uuid.uuid4()}"}


async def _records_of(engine: AsyncEngine, who: Person) -> None:
    async with engine.begin() as conn:
        await _new(conn, Rrotor, **_self(who))
        gh = {"user_id": who.user_id, "installation_id": uuid.uuid4().int % 10**12, "account_login": "octo"}
        await _new(conn, GitHubInstallation, **gh)


async def test_a_tenant_sees_only_its_own_runtimes(engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    for who in (ada, eve):
        await _records_of(engine, who)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        for table in TABLES:
            assert (await conn.execute(select(func.count()).select_from(table))).scalar_one() == 1, table


async def _refused(engine: AsyncEngine, constraint: str, table: type, **values: object) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        async with engine.begin() as conn:
            await conn.execute(insert(table).values(**values))


async def test_runtimes_are_local_per_install_or_self_hosted_at_one_address(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    await _records_of(engine, ada)
    await _refused(engine, "rrotors_self_url", Rrotor, **_self(ada) | {"token_hash": "another"})
    await _refused(engine, "rrotors_self_address", Rrotor, **_self(ada) | {"token_hash": "t2", "public_url": None})
    await _refused(engine, "rrotors_local_install", Rrotor, **_self(ada) | {"install_id": ada.install_id})
    await _refused(engine, "rrotors_local_install", Rrotor, **_local(ada, ada.install_id) | {"install_id": None})
    for mode in ("hosted", "cloud"):
        await _refused(engine, "rrotors_mode", Rrotor, **_self(ada) | {"mode": mode, "token_hash": mode})
    linux, _ = await another_install(engine, ada.user_id)
    async with engine.begin() as conn:
        await conn.execute(insert(Rrotor).values(**_local(ada, ada.install_id)))
        await conn.execute(insert(Rrotor).values(**_local(ada, linux)))
    await _refused(engine, "rrotors_install_id_key", Rrotor, **_local(ada, ada.install_id))
    gh = {"user_id": ada.user_id, "installation_id": 1, "account_login": "octo"}
    await _refused(engine, "github_installations_user_id_key", GitHubInstallation, **gh)
