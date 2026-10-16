"""The routine triggers a person gives Glyphh: kept with the token sealed, listed without it, deleted one by one."""

import uuid

import httpx
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Model, RoutineTrigger
from glyphh_server.ops import vault
from glyphh_server.ops.routine_triggers import sealed_for
from tests.conftest import PROVIDER_SETTINGS, SECRETS_KEY, _client
from tests.db.helpers import Person, person

FIRE: str = "https://api.anthropic.com/v1/claude_code/routines/trig_01ABCdef/fire"
TOKEN: str = "sk-ant-oat01-not-a-real-routine-token"


async def _model(engine: AsyncEngine, who: Person) -> str:
    async with engine.begin() as conn:
        values = {"user_id": who.user_id, "org_id": who.org_id, "name": "daily_sales"}
        return str((await conn.execute(insert(Model).values(values).returning(Model.id))).scalar_one())


def _new(**over: object) -> dict[str, object]:
    return {"name": "Daily sales", "fire_url": FIRE, "token": TOKEN, **over}


async def test_a_trigger_is_kept_sealed_listed_without_its_token_and_deleted(
    engine: AsyncEngine, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    model_id = await _model(engine, ada)
    made = await client.post("/v1/routine-triggers", json=_new(model_id=model_id), headers=ada.headers)
    assert made.status_code == 201, made.text
    view = made.json()
    assert (view["name"], view["model_id"], view["status"], view["last_fired_at"]) == (
        "Daily sales",
        model_id,
        "ok",
        None,
    )
    bare = await client.post("/v1/routine-triggers", json=_new(name="  Any  "), headers=ada.headers)
    listed = await client.get("/v1/routine-triggers", headers=ada.headers)
    assert [t["name"] for t in listed.json()] == ["Daily sales", "Any"] and bare.json()["model_id"] is None
    assert TOKEN not in made.text + bare.text + listed.text and "token" not in listed.json()[0]
    async with engine.connect() as conn:
        sealed = (await conn.execute(select(RoutineTrigger.token_enc).where(RoutineTrigger.id == view["id"]))).scalar()
    assert TOKEN not in sealed
    assert vault.unseal(vault.load_key(PROVIDER_SETTINGS), sealed, sealed_for(ada.user_id, FIRE)) == TOKEN
    assert (await client.delete(f"/v1/routine-triggers/{view['id']}", headers=ada.headers)).status_code == 204
    gone = await client.delete(f"/v1/routine-triggers/{view['id']}", headers=ada.headers)
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "E_NOT_FOUND"
    assert [t["name"] for t in (await client.get("/v1/routine-triggers", headers=ada.headers)).json()] == ["Any"]


async def test_only_anthropics_fire_address_and_ones_own_model_are_taken(
    engine: AsyncEngine, client: httpx.AsyncClient
) -> None:
    ada, eve = await person(engine), await person(engine)
    for url in (
        FIRE.replace("https", "http"),
        FIRE.replace("api.anthropic.com", "api.anthropic.com.evil.test"),
        FIRE + "/more",
        FIRE.replace("trig_01ABCdef", "../x"),
    ):
        res = await client.post("/v1/routine-triggers", json=_new(fire_url=url), headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID", url
    for bad in (_new(name=" "), _new(token=""), _new(model_id="nope")):
        assert (await client.post("/v1/routine-triggers", json=bad, headers=ada.headers)).status_code == 422
    theirs = await _model(engine, eve)
    res = await client.post("/v1/routine-triggers", json=_new(model_id=theirs), headers=ada.headers)
    assert res.status_code == 404 and res.json()["error"]["code"] == "E_NOT_FOUND"
    unknown = await client.post("/v1/routine-triggers", json=_new(model_id=str(uuid.uuid4())), headers=ada.headers)
    assert unknown.status_code == 404


async def test_another_persons_triggers_are_neither_seen_nor_deleted(
    engine: AsyncEngine, client: httpx.AsyncClient
) -> None:
    ada, eve = await person(engine), await person(engine)
    made = (await client.post("/v1/routine-triggers", json=_new(), headers=ada.headers)).json()
    assert (await client.get("/v1/routine-triggers", headers=eve.headers)).json() == []
    assert (await client.delete(f"/v1/routine-triggers/{made['id']}", headers=eve.headers)).status_code == 404
    assert len((await client.get("/v1/routine-triggers", headers=ada.headers)).json()) == 1
    assert (await client.get("/v1/routine-triggers")).status_code == 401


async def test_without_a_secrets_key_triggers_are_not_taken(engine: AsyncEngine) -> None:
    ada = await person(engine)
    assert SECRETS_KEY
    async for bare in _client(create_app(PROVIDER_SETTINGS.model_copy(update={"secrets_key": ""}))):
        res = await bare.post("/v1/routine-triggers", json=_new(), headers=ada.headers)
        assert res.status_code == 503 and res.json()["error"]["code"] == "E_UNAVAILABLE"
        assert (await bare.get("/v1/routine-triggers", headers=ada.headers)).json() == []
