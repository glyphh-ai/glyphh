"""A local rrotor's runtime token, from the install that starts it: one runtime per install, rotated on asking again."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.secrets import hash_secret
from tests.db.helpers import another_install, person


async def _runtime(engine: AsyncEngine, runtime_id: str):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Rrotor).where(Rrotor.id == uuid.UUID(runtime_id)))).one()


async def test_an_install_gets_its_local_runtime_and_a_new_token_each_time(
    engine: AsyncEngine, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    first = await client.post("/v1/runtime/local", headers=ada.headers)
    assert first.status_code == 200, first.text
    made = first.json()
    row = await _runtime(engine, made["runtime_id"])
    assert (row.mode, row.install_id, row.user_id, row.state) == ("local", ada.install_id, ada.user_id, "stopped")
    assert row.token_hash == hash_secret(made["token"]) and row.region is None and row.fly_machine_id is None
    again = (await client.post("/v1/runtime/local", headers=ada.headers)).json()
    assert again["runtime_id"] == made["runtime_id"] and again["token"] != made["token"]
    assert (await _runtime(engine, made["runtime_id"])).token_hash == hash_secret(again["token"])
    _, linux = await another_install(engine, ada.user_id)
    other = (await client.post("/v1/runtime/local", headers=linux)).json()
    assert other["runtime_id"] != made["runtime_id"]


async def test_a_local_runtime_needs_an_install_token(client: httpx.AsyncClient) -> None:
    res = await client.post("/v1/runtime/local")
    assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"
