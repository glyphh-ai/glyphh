"""What other code sends down a runtime's link: each finds only the caller's own runtimes and runs, refuses what does
not fit the run's state, and answers E_UNAVAILABLE, rolled back, when no process holds the link. Deploys carry a
repo token only for a model in git. The hub's link answers False for a socket already gone."""

import random
import uuid
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound, Unavailable
from glyphh_server.models import Deployment, GitHubInstallation, Rrotor, Run
from glyphh_server.ops import github_app
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.link.calls import send_call, send_cancel, send_continue, send_deploy
from glyphh_server.ops.link.hub import Hub, Link
from tests.conftest import GITHUB_APP_ID, GITHUB_APP_KEY, SETTINGS
from tests.db.helpers import Person, person
from tests.fakes import FakeGitHubApp, fake_http
from tests.link import SHA2, a_model, deploy, holding, hosted_runtime, local_runtime


async def _runs(engine: AsyncEngine, runtime_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).where(Run.rrotor_id == runtime_id))).scalar_one()


async def test_a_call_finds_only_ones_own_runtime_and_a_version_it_has(engine: AsyncEngine, redis: Redis) -> None:
    ada, eve = await person(engine), await person(engine)
    rt, eves = await local_runtime(engine, ada), await local_runtime(engine, eve)
    model_id, _, _ = await a_model(engine, ada)
    hub = Hub(redis)
    for runtime_id, version, why in ((eves.id, 1, "no such runtime"), (rt.id, None, "no such version")):
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            with pytest.raises(NotFound, match=why):
                await send_call(conn, hub, runtime_id, model_id, version, "start", {}, "routine")
    async with holding(redis, rt.id) as sent, engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        run_id = await send_call(conn, hub, rt.id, model_id, 2, "fetch_leads", {"since": "monday"}, "routine")
        call = await sent()
    assert (call["run_id"], call["version"], call["function"], call["caller"]) == (
        str(run_id),
        2,
        "fetch_leads",
        "routine",
    )


async def test_a_runtime_nobody_holds_is_unavailable_with_when_it_was_seen_and_nothing_is_kept(
    engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine, "Pro")
    local, hosted = await local_runtime(engine, ada), await hosted_runtime(engine, ada)
    model_id, v1, _ = await a_model(engine, ada)
    seen = datetime(2026, 10, 14, 7, 7, tzinfo=UTC)
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == local.id).values(last_seen_at=seen, state="offline"))
    for rt, reason, last_seen in ((local, "runtime_offline", seen.isoformat()), (hosted, "runtime_stopped", None)):
        await deploy(engine, rt.id, v1)
        with pytest.raises(Unavailable) as refused:
            async with engine.begin() as conn:
                await tenancy.enter(conn, ada.org_id)
                await send_call(conn, Hub(redis), rt.id, model_id, None, "start", {}, "claude")
        assert refused.value.detail == {"reason": reason, "runtime_id": str(rt.id), "last_seen_at": last_seen}
        assert await _runs(engine, rt.id) == 0


async def _a_run(engine: AsyncEngine, who: Person, status: str) -> tuple[uuid.UUID, uuid.UUID]:
    rt = await local_runtime(engine, who)
    _, v1, _ = await a_model(engine, who)
    values = {"model_version_id": v1, "rrotor_id": rt.id, "function": "start", "caller": "test", "status": status}
    async with engine.begin() as conn:
        return (await conn.execute(insert(Run).values(values).returning(Run.id))).scalar_one(), rt.id


async def test_continue_needs_a_waiting_run_and_cancel_one_not_ended(engine: AsyncEngine, redis: Redis) -> None:
    ada = await person(engine)
    done, _ = await _a_run(engine, ada, "done")
    running, runtime_id = await _a_run(engine, ada, "running")
    hub = Hub(redis)
    cases = (
        (send_continue, (uuid.uuid4(), {}), NotFound),
        (send_continue, (running, {"x": 1}), Conflict),
        (send_cancel, (done,), Conflict),
    )
    for send, args, error in cases:
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            with pytest.raises(error):
                await send(conn, hub, *args)  # type: ignore[operator]
    async with holding(redis, runtime_id) as sent, engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        await send_cancel(conn, hub, running)
        assert {k: v for k, v in (await sent()).items() if k != "id"} == {"type": "cancel", "run_id": str(running)}


def _github() -> tuple[GitHubApp, FakeGitHubApp]:
    fake = FakeGitHubApp(GITHUB_APP_KEY.public_key(), GITHUB_APP_ID)
    return GitHubApp(fake_http(github_app=fake), SETTINGS, github_app.load_key(SETTINGS)), fake


async def test_a_deploy_carries_a_repo_token_only_for_a_model_in_git(engine: AsyncEngine, redis: Redis) -> None:
    ada = await person(engine, "Pro")
    rt = await hosted_runtime(engine, ada)
    _, local_v1, _ = await a_model(engine, ada, name="local_only")
    _, _, git_v2 = await a_model(engine, ada, name="daily_sales", repo="octo/daily_sales")
    installation = random.randint(10**6, 10**9)
    app, fake = _github()
    fake.install(installation, 4242, "octo")
    async with engine.begin() as conn:
        values = {"user_id": ada.user_id, "installation_id": installation, "account_login": "octo"}
        await conn.execute(insert(GitHubInstallation).values(values))
    await deploy(engine, rt.id, git_v2)
    hub = Hub(redis)
    sends = [(local_v1, "deploy", None), (git_v2, "activate", "ghs_fake_repo_token"), (git_v2, "remove", None)]
    async with holding(redis, rt.id) as sent:
        for version_id, action, token in sends:
            async with engine.begin() as conn:
                await tenancy.enter(conn, ada.org_id)
                await send_deploy(conn, hub, app, rt.id, version_id, action)  # type: ignore[arg-type]
            message = await sent()
            assert (message["type"], message["token"]) == (action, token)
    assert message == {
        **message,
        "model": "daily_sales",
        "version": 2,
        "repo": "octo/daily_sales",
        "commit_sha": SHA2,
    }
    async with engine.connect() as conn:
        assert (await conn.execute(select(Deployment).where(Deployment.rrotor_id == rt.id))).all() == []
    for github, version_id, error in ((None, git_v2, Unavailable), (app, uuid.uuid4(), NotFound)):
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            with pytest.raises(error):
                await send_deploy(conn, hub, github, rt.id, version_id)


class _Gone:
    """A WebSocket the rrotor already hung up."""

    async def send_text(self, _: str) -> None:
        raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def close(self, code: int, reason: str) -> None:
        raise RuntimeError("closed")


async def test_a_link_already_gone_answers_false_and_closes_quietly(redis: Redis) -> None:
    hub = Hub(redis)
    link = Link(_Gone(), uuid.uuid4())  # type: ignore[arg-type]
    hub.links[link.runtime_id] = link
    assert await hub.deliver(link.runtime_id, {"type": "ping", "id": "p"}) is False
    await link.close(1000, "bye")
    hub.detach(Link(_Gone(), link.runtime_id))  # type: ignore[arg-type]  # not the one held: kept
    assert hub.links[link.runtime_id] is link
