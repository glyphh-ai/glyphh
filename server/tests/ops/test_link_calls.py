"""What other code sends down a runtime's link (an approval's answer, a deploy): each finds only the caller's own
runtimes and runs, refuses what does not fit the run's state, answers E_UNAVAILABLE, rolled back, when no process
holds a local runtime's link, and wakes a stopped hosted one. Deploys carry a repo token only for a model in git.
The hub's link answers False for a socket already gone."""

import asyncio
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
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.calls import send_continue, send_deploy
from glyphh_server.ops.link.hub import Hub, Link
from tests.conftest import GITHUB_APP_ID, GITHUB_APP_KEY, SETTINGS
from tests.db.helpers import Person, person
from tests.fakes import FakeGitHubApp, fake_http
from tests.link import SHA2, a_model, deploy, holding, hosted_runtime, local_runtime


async def _runs(engine: AsyncEngine, runtime_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).where(Run.rrotor_id == runtime_id))).scalar_one()


async def _a_run(engine: AsyncEngine, who: Person, status: str) -> tuple[uuid.UUID, uuid.UUID]:
    rt = await local_runtime(engine, who)
    _, v1, _ = await a_model(engine, who)
    values = {"model_version_id": v1, "rrotor_id": rt.id, "function": "start", "caller": "test", "status": status}
    async with engine.begin() as conn:
        return (await conn.execute(insert(Run).values(values).returning(Run.id))).scalar_one(), rt.id


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
    with pytest.raises(NotFound, match="no such runtime"):
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            await send_deploy(conn, hub, app, uuid.uuid4(), git_v2)
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


async def test_continue_needs_a_waiting_run_the_callers_own_and_a_link_or_keeps_nothing(
    engine: AsyncEngine, redis: Redis
) -> None:
    ada, eve = await person(engine), await person(engine)
    done, _ = await _a_run(engine, ada, "done")
    waiting, runtime_id = await _a_run(engine, ada, "needs_input")
    seen = datetime(2026, 10, 14, 7, 7, tzinfo=UTC)
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(last_seen_at=seen, state="offline"))
    hub = Hub(redis)
    for who, run_id, error in ((ada, uuid.uuid4(), NotFound), (ada, done, Conflict), (eve, waiting, NotFound)):
        async with engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            with pytest.raises(error):
                await send_continue(conn, hub, run_id, {"x": 1})
    with pytest.raises(Unavailable) as refused:
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            await send_continue(conn, hub, waiting, "yes")
    assert refused.value.message == calls.AWAY["local"]
    assert refused.value.detail == {
        "reason": "runtime_offline",
        "runtime_id": str(runtime_id),
        "last_seen_at": seen.isoformat(),
    }
    async with engine.connect() as conn:
        assert (await conn.execute(select(Run.status).where(Run.id == waiting))).scalar_one() == "needs_input"
    async with holding(redis, runtime_id) as sent, engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        await send_continue(conn, hub, waiting, "yes")
        message = await sent()
    assert (message["type"], message["run_id"], message["answer"]) == ("continue", str(waiting), "yes")


async def test_a_stopped_hosted_runtime_is_woken_for_an_approvals_answer(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(calls, "WAKE_EVERY", 0.02)
    monkeypatch.setattr(calls, "WAKE_WAIT", 2.0)
    ada = await person(engine, "Pro")
    rt = await hosted_runtime(engine, ada)
    _, v1, _ = await a_model(engine, ada)
    values = {"model_version_id": v1, "rrotor_id": rt.id, "function": "start", "caller": "claude"}
    async with engine.begin() as conn:
        run_id = (
            await conn.execute(insert(Run).values(**values, status="needs_approval").returning(Run.id))
        ).scalar_one()
    woken: list[uuid.UUID] = []
    heard: list[dict] = []
    linked = asyncio.Event()

    async def rrotor_links() -> None:
        async with holding(redis, rt.id) as sent:
            linked.set()
            heard.append(await sent())

    async def wake(runtime_id: uuid.UUID) -> None:
        woken.append(runtime_id)
        asyncio.get_running_loop().create_task(rrotor_links())  # the machine starts, its rrotor links a beat later
        await linked.wait()

    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        await send_continue(conn, Hub(redis, waker=wake), run_id, {"approved": True})
    assert woken == [rt.id] and heard[0]["run_id"] == str(run_id)
    for waker, reason in ((None, "hosting_off"), (wake, "runtime_offline")):
        monkeypatch.setattr(calls, "WAKE_WAIT", 0.05)
        linked.clear()

        async def never(runtime_id: uuid.UUID) -> None:
            woken.append(runtime_id)

        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            await conn.execute(update(Run).where(Run.id == run_id).values(status="needs_approval"))
        with pytest.raises(Unavailable) as refused:
            async with engine.begin() as conn:
                await tenancy.enter(conn, ada.org_id)
                await send_continue(conn, Hub(redis, waker=never if waker else None), run_id, "x")
        assert refused.value.detail["reason"] == reason
        if waker:  # woken, never linked: said as a hosted machine, never as a local runtime
            assert refused.value.message == calls.AWAY["hosted"]
