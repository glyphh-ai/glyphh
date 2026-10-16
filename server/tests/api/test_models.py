"""Models: made within Ada's limit (none without Ada), named once each, versioned one commit at a time, listed with
where each version is active, deployed to the caller's own runtime down its link, and deleted with everything theirs."""

import uuid

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, person, with_addon
from tests.fakes import fake_http
from tests.link import SHA, SHA2, deploy, holding, local_runtime


async def with_ada(engine: AsyncEngine) -> Person:
    ada = await person(engine, "Pro")
    await with_addon(engine, ada.org_id, "ada")
    return ada


def _error(res: httpx.Response, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    error = res.json()["error"]
    assert error["code"] == code, error
    return error


async def test_models_are_made_within_adas_limit_and_none_without_ada(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await with_ada(engine)
    for name in ("leads", "tickets", "sales"):
        made = await client.post("/v1/models", json={"name": name}, headers=ada.headers)
        assert made.status_code == 201, made.text
        assert (made.json()["name"], made.json()["repo"], made.json()["versions"]) == (name, None, [])
    full = _error(await client.post("/v1/models", json={"name": "more"}, headers=ada.headers), 403, "E_LIMIT")
    assert (full["limit"], full["used"], full["max"], full["plan"]) == ("models", 3, 3, None)
    assert full["message"] == "Ada allows you 3 models. Remove one first."
    free = await person(engine)
    none = _error(await client.post("/v1/models", json={"name": "leads"}, headers=free.headers), 403, "E_FORBIDDEN")
    assert none["reason"] == "no_ada"
    listed = await client.get("/v1/models", headers=ada.headers)
    assert [m["name"] for m in listed.json()] == ["leads", "tickets", "sales"]
    assert (await client.get("/v1/models", headers=free.headers)).json() == []
    bad = await client.post("/v1/models", json={"name": "leads", "repo": "not a repo"}, headers=ada.headers)
    assert bad.status_code == 422


async def test_a_name_is_used_once_and_each_commit_is_one_version(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await with_ada(engine)
    made = await client.post("/v1/models", json={"name": "leads", "repo": "octo/leads"}, headers=ada.headers)
    model_id = made.json()["id"]
    taken = _error(await client.post("/v1/models", json={"name": "leads"}, headers=ada.headers), 409, "E_CONFLICT")
    assert (taken["reason"], taken["model"]) == ("name_taken", "leads")
    versions = f"/v1/models/{model_id}/versions"
    v1 = await client.post(versions, json={"commit_sha": SHA, "manifest": {"name": "leads"}}, headers=ada.headers)
    v2 = await client.post(versions, json={"commit_sha": SHA2, "manifest": {}}, headers=ada.headers)
    assert (v1.status_code, v1.json()["version"], v2.json()["version"], v2.json()["commit_sha"]) == (201, 1, 2, SHA2)
    again = await client.post(versions, json={"commit_sha": SHA, "manifest": {}}, headers=ada.headers)
    assert (_error(again, 409, "E_CONFLICT")["reason"], again.json()["error"]["version"]) == ("commit_known", 1)
    short = await client.post(versions, json={"commit_sha": "abc", "manifest": {}}, headers=ada.headers)
    assert short.status_code == 422
    rt = await local_runtime(engine, ada)
    await deploy(engine, rt.id, v2.json()["id"])
    got = (await client.get(f"/v1/models/{model_id}", headers=ada.headers)).json()
    assert (got["repo"], [v["version"] for v in got["versions"]]) == ("octo/leads", [1, 2])
    assert [v["active_on"] for v in got["versions"]] == [[], [str(rt.id)]]
    eve = await with_ada(engine)
    for method, path in (("GET", f"/v1/models/{model_id}"), ("DELETE", f"/v1/models/{model_id}"), ("POST", versions)):
        body = {"commit_sha": SHA, "manifest": {}} if method == "POST" else None
        _error(await client.request(method, path, json=body, headers=eve.headers), 404, "E_NOT_FOUND")
    assert (await client.delete(f"/v1/models/{model_id}", headers=ada.headers)).status_code == 204
    _error(await client.get(f"/v1/models/{model_id}", headers=ada.headers), 404, "E_NOT_FOUND")
    assert (await client.get("/v1/models", headers=ada.headers)).json() == []


async def test_a_deploy_goes_down_the_callers_runtimes_link(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await with_ada(engine)
    model = (await client.post("/v1/models", json={"name": "leads"}, headers=ada.headers)).json()
    versions = f"/v1/models/{model['id']}/versions"
    await client.post(versions, json={"commit_sha": SHA, "manifest": {}}, headers=ada.headers)
    path = f"/v1/models/{model['id']}/deploy"
    nowhere = _error(await client.post(path, json={"version": 1}, headers=ada.headers), 404, "E_NOT_FOUND")
    assert nowhere["reason"] == "no_runtime"
    rt = await local_runtime(engine, ada)
    _error(await client.post(path, json={"version": 2}, headers=ada.headers), 404, "E_NOT_FOUND")
    off = _error(await client.post(path, json={"version": 1}, headers=ada.headers), 503, "E_UNAVAILABLE")
    assert off["reason"] == "runtime_offline"
    async with holding(redis, rt.id) as sent:
        for action in ("deploy", "activate", "remove"):
            res = await client.post(path, json={"version": 1, "action": action}, headers=ada.headers)
            assert res.status_code == 200, res.text
            assert res.json() == {"model": "leads", "version": 1, "runtime_id": str(rt.id), "action": action}
            message = await sent()
            assert (message["type"], message["model"], message["commit_sha"], message["token"]) == (
                action,
                "leads",
                SHA,
                None,
            )
        named = await client.post(path, json={"version": 1, "runtime_id": str(rt.id)}, headers=ada.headers)
        assert named.status_code == 200 and (await sent())["type"] == "deploy"
    eve = await with_ada(engine)
    theirs = await local_runtime(engine, eve)
    other = _error(
        await client.post(path, json={"version": 1, "runtime_id": str(theirs.id)}, headers=ada.headers),
        404,
        "E_NOT_FOUND",
    )
    assert other["runtime_id"] == str(theirs.id)
    _error(await client.post(path, json={"version": 1}, headers=eve.headers), 404, "E_NOT_FOUND")
    _error(
        await client.post(path, json={"version": 1, "runtime_id": str(uuid.uuid4())}, headers=ada.headers),
        404,
        "E_NOT_FOUND",
    )


async def test_a_model_in_git_needs_the_github_app_set_up(engine: AsyncEngine, redis: Redis) -> None:
    ada = await with_ada(engine)
    rt = await local_runtime(engine, ada)
    settings = PROVIDER_SETTINGS.model_copy(update={"github_app_id": None})
    async for client in _client(create_app(settings, http=fake_http())):
        model = (
            await client.post("/v1/models", json={"name": "leads", "repo": "octo/leads"}, headers=ada.headers)
        ).json()
        await client.post(
            f"/v1/models/{model['id']}/versions", json={"commit_sha": SHA, "manifest": {}}, headers=ada.headers
        )
        async with holding(redis, rt.id):
            res = await client.post(f"/v1/models/{model['id']}/deploy", json={"version": 1}, headers=ada.headers)
        assert _error(res, 503, "E_UNAVAILABLE")["reason"] == "github_off"
