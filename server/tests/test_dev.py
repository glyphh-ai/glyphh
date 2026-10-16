"""The development command: a hosted runtime for a person without Fly, its token shown once and rotated on asking
again; nobody of that email is refused; prod is refused."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import dev
from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.secrets import hash_secret
from tests.conftest import SETTINGS
from tests.db.helpers import person


async def test_a_hosted_runtime_is_made_for_the_person_and_its_token_rotated(
    engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    ada = await person(engine)
    assert await dev.run(["runtime", ada.email, "--host", "dev.ngrok-free.app"], SETTINGS) == 0
    env = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    assert (env["RROTOR_MODE"], env["RROTOR_SERVER"], env["RROTOR_PUBLIC_HOST"]) == (
        "hosted",
        SETTINGS.base_url,
        "dev.ngrok-free.app",
    )
    async with engine.connect() as conn:
        row = (await conn.execute(select(Rrotor).where(Rrotor.id == uuid.UUID(env["RROTOR_RUNTIME_ID"])))).one()
    assert (row.mode, row.user_id, row.region, row.token_hash) == (
        "hosted",
        ada.user_id,
        "local",
        hash_secret(env["RROTOR_RUNTIME_TOKEN"]),
    )
    assert await dev.run(["runtime", ada.email], SETTINGS) == 0
    again = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    assert (
        again["RROTOR_RUNTIME_ID"] == env["RROTOR_RUNTIME_ID"]
        and again["RROTOR_RUNTIME_TOKEN"] != env["RROTOR_RUNTIME_TOKEN"]
    )
    assert again["RROTOR_PUBLIC_HOST"] == "<your ngrok name>"
    async with engine.connect() as conn:
        row = (await conn.execute(select(Rrotor).where(Rrotor.id == row.id))).one()
    assert row.token_hash == hash_secret(again["RROTOR_RUNTIME_TOKEN"])
    with pytest.raises(SystemExit, match="nobody signed in"):
        await dev.run(["runtime", "nobody@people.test"], SETTINGS)
    assert await dev.run(["runtime", ada.email], SETTINGS.model_copy(update={"env": "prod"})) == 2
    assert "development only" in capsys.readouterr().err
