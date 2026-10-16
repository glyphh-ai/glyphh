"""What other code sends down a runtime's link: a call, a continue, a cancel, a deploy.

Each runs in the caller's transaction, as the caller's org, so only the caller's own runtimes and runs are found. A
run is held (hold_run) before its message goes down, so its result is applied only once the caller commits;
a message that cannot go raises, and the caller's transaction, a new run's row too, rolls back. A local runtime no
process holds answers E_UNAVAILABLE with when it was last seen; a hosted one is woken (its Fly machine started, by
the hub's waker) and the message waits for its link, up to WAKE_WAIT."""

import uuid
from typing import Any, Literal

import anyio
from sqlalchemy import Row, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound, Unavailable
from glyphh_server.models import Deployment, Model, ModelVersion, Rrotor, Run
from glyphh_server.ops.auth.signin import lock
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.github_installations import repo_token
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import FINAL, RUNNING, WAITING, Call, Cancel, Continue, Deploy, Outbound

DeployAction = Literal["deploy", "activate", "remove"]
WAKE_WAIT: float = 45.0  # a stopped Fly machine starts in seconds; its rrotor links in a few more
WAKE_EVERY: float = 0.5


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
        "Your local runtime is not connected. Start it from Claude, then try again.",
        reason="runtime_offline",
        runtime_id=str(runtime.id),
        last_seen_at=_seen(runtime),
    )


async def _version(conn: AsyncConnection, runtime_id: uuid.UUID, model_id: uuid.UUID, version: int | None) -> Row:
    """That version of the model, or, with none named, the one active on this runtime."""
    found = (
        select(ModelVersion.id, ModelVersion.version, Model.name)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(Model.id == model_id)
    )
    if version is None:
        found = found.join(Deployment, Deployment.model_version_id == ModelVersion.id).where(
            Deployment.rrotor_id == runtime_id, Deployment.active.is_(True)
        )
    else:
        found = found.where(ModelVersion.version == version)
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("That model has no such version on this runtime.", model_id=str(model_id))
    return row


async def send_call(
    conn: AsyncConnection,
    hub: Hub,
    runtime_id: uuid.UUID,
    model_id: uuid.UUID,
    version: int | None,
    function: str,
    inputs: dict[str, Any],
    caller: str,
    clearance: float = 1.0,
) -> uuid.UUID:
    """Open a run: its row (running), then `call` down the runtime's link, with the caller's clearance (0 to 1; 1 is
    the person themself). Answers the run's id."""
    runtime = await _runtime(conn, runtime_id)
    found = await _version(conn, runtime_id, model_id, version)
    values = {"model_version_id": found.id, "rrotor_id": runtime_id, "function": function, "caller": caller}
    run_id = (await conn.execute(insert(Run).values(**values, status=RUNNING).returning(Run.id))).scalar_one()
    await hold_run(conn, run_id)
    message = Call(
        run_id=run_id,
        model=found.name,
        version=found.version,
        function=function,
        inputs=inputs,
        caller=caller,
        clearance=clearance,
    )
    await deliver(hub, runtime, message)
    return run_id


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


async def send_cancel(conn: AsyncConnection, hub: Hub, run_id: uuid.UUID) -> None:
    """Stop a run; the rrotor runs its `end` and answers its result, `cancelled`."""
    run = await _held_run(conn, run_id)
    if run.status in FINAL:
        raise Conflict("This run has ended.", run_id=str(run_id), status=run.status)
    await deliver(hub, await _runtime(conn, run.rrotor_id), Cancel(run_id=run_id))


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
