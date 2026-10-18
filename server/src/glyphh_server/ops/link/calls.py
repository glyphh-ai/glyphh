"""What other code sends down a runtime's link: an approval's answer (`continue`) and a deploy. Calls never go
down it: a runtime is called at its own address (docs, Reaching a runtime).

Each runs in the caller's transaction, as the caller's org, so only the caller's own runtimes and runs are found. A
run is held (hold_run) before its message goes down, so its result is applied only once the caller commits; a
message that cannot go raises, and the caller's transaction rolls back. A hosted runtime no process holds is woken
(its Fly machine started, by the hub's waker) and the message waits for its link, up to WAKE_WAIT; one that never
links, a local one or a self-hosted one answers E_UNAVAILABLE with when it was last seen, in its own words (AWAY)."""

import uuid
from typing import Any, Literal

import anyio
from sqlalchemy import Row, delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound, Unavailable
from glyphh_server.models import Deployment, Model, ModelVersion, Rrotor, Run
from glyphh_server.ops.auth.signin import lock
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.github_installations import repo_token
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import RUNNING, WAITING, Continue, Deploy, Outbound

DeployAction = Literal["deploy", "activate", "remove"]
WAKE_WAIT: float = 45.0  # a stopped Fly machine starts in seconds; its rrotor links in a few more
WAKE_EVERY: float = 0.5
AWAY: dict[str, str] = {
    "hosted": "Your hosted machine was started but did not connect in time. Try again in a minute.",
    "local": "Your local runtime is not connected. Start it from Claude, then try again.",
    "self": "Your self-hosted runtime is not connected. Check it is running and reaches Glyphh, then try again.",
}


async def hold_run(conn: AsyncConnection, run_id: uuid.UUID) -> None:
    """One transaction at a time per run: a result waits until the call or continue that caused it is committed."""
    await lock(conn, f"run:{run_id}")


async def _runtime(conn: AsyncConnection, runtime_id: uuid.UUID) -> Row:
    found = select(Rrotor.id, Rrotor.mode, Rrotor.last_seen_at).where(Rrotor.id == runtime_id)
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("You have no such runtime.", runtime_id=str(runtime_id))
    return row


def _seen(runtime: Row) -> str | None:
    return runtime.last_seen_at.isoformat() if runtime.last_seen_at else None


async def wake_hosted(hub: Hub, runtime: Row, message: dict[str, Any]) -> bool:
    """Start a hosted runtime's machine and deliver once its link is up; False when it never came up in time."""
    if hub.waker is None:
        raise Unavailable(
            "Your hosted runtime is stopped, and hosting isn't set up on this server.",
            reason="hosting_off",
            runtime_id=str(runtime.id),
        )
    await hub.waker(runtime.id)
    with anyio.move_on_after(WAKE_WAIT):
        while True:
            await anyio.sleep(WAKE_EVERY)
            if await hub.deliver(runtime.id, message):
                return True
    return False


async def deliver(hub: Hub, runtime: Row, message: Outbound) -> None:
    data = message.model_dump(mode="json")
    if await hub.deliver(runtime.id, data):
        return
    if runtime.mode == "hosted" and await wake_hosted(hub, runtime, data):
        return
    raise Unavailable(
        AWAY[runtime.mode],
        reason="runtime_offline",
        runtime_id=str(runtime.id),
        last_seen_at=_seen(runtime),
    )


async def _held_run(conn: AsyncConnection, run_id: uuid.UUID) -> Row:
    await hold_run(conn, run_id)
    row = (await conn.execute(select(Run.rrotor_id, Run.status).where(Run.id == run_id))).first()
    if row is None:
        raise NotFound("You have no such run.", run_id=str(run_id))
    return row


async def send_continue(conn: AsyncConnection, hub: Hub, run_id: uuid.UUID, answer: Any) -> None:
    """Resume a run waiting for an answer (input, approval, sign-in): it is running again."""
    run = await _held_run(conn, run_id)
    if run.status not in WAITING:
        raise Conflict("This run is not waiting for an answer.", run_id=str(run_id), status=run.status)
    await conn.execute(update(Run).where(Run.id == run_id).values(status=RUNNING))
    await deliver(hub, await _runtime(conn, run.rrotor_id), Continue(run_id=run_id, answer=answer))


async def send_deploy(
    conn: AsyncConnection,
    hub: Hub,
    github: GitHubApp | None,
    runtime_id: uuid.UUID,
    version_id: uuid.UUID,
    action: DeployAction = "deploy",
) -> None:
    """Deploy, activate or remove one version on a runtime. A model in git gets a one-hour token for its repo, to
    fetch exactly that commit; the rrotor answers `deployed`. Removing it drops its deployment here at once."""
    runtime = await _runtime(conn, runtime_id)
    found = (
        select(ModelVersion.version, ModelVersion.commit_sha, Model.name, Model.repo, Model.user_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(ModelVersion.id == version_id)
    )
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("You have no such model version.", version_id=str(version_id))
    token = None
    if row.repo and action != "remove":
        if github is None:
            raise Unavailable("GitHub isn't set up on this server.", reason="github_off")
        token = (await repo_token(conn, github, row.user_id, row.repo)).token
    if action == "remove":
        gone = delete(Deployment).where(Deployment.rrotor_id == runtime_id, Deployment.model_version_id == version_id)
        await conn.execute(gone)
    message = Deploy(
        type=action, model=row.name, version=row.version, repo=row.repo, commit_sha=row.commit_sha, token=token
    )
    await deliver(hub, runtime, message)
