"""What other code sends down a runtime's link: a call, a continue, a cancel, a deploy.

Each runs in the caller's transaction, as the caller's org, so only the caller's own runtimes and runs are found. A
run is held (hold_run) before its message goes down, so its result is applied only once the caller commits;
a message that cannot go raises, and the caller's transaction, a new run's row too, rolls back. A runtime no process
holds answers E_UNAVAILABLE with when it was last seen. Waking a stopped hosted runtime on Fly is one seam,
`wake_hosted`, not built in this pass."""

import uuid
from typing import Any, Literal

from sqlalchemy import Row, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound, Unavailable
from glyphh_server.models import Deployment, Program, ProgramVersion, Rrotor, Run
from glyphh_server.ops.auth.signin import lock
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.github_installations import repo_token
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import FINAL, RUNNING, WAITING, Call, Cancel, Continue, Deploy, Outbound

DeployAction = Literal["deploy", "activate", "remove"]


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


async def wake_hosted(runtime: Row) -> None:
    """The seam for a stopped hosted runtime: start its Fly machine, wait for its link, then deliver again.

    Not built in this pass (there is no Fly client yet): the call is refused, saying so."""
    raise Unavailable(
        "Your hosted runtime is stopped, and waking it is not built yet.",
        reason="runtime_stopped",
        runtime_id=str(runtime.id),
        last_seen_at=_seen(runtime),
    )


async def deliver(hub: Hub, runtime: Row, message: Outbound) -> None:
    if await hub.deliver(runtime.id, message.model_dump(mode="json")):
        return
    if runtime.mode == "hosted":
        await wake_hosted(runtime)
    raise Unavailable(
        "Your local runtime is not connected. Start it from Claude, then try again.",
        reason="runtime_offline",
        runtime_id=str(runtime.id),
        last_seen_at=_seen(runtime),
    )


async def _version(conn: AsyncConnection, runtime_id: uuid.UUID, program_id: uuid.UUID, version: int | None) -> Row:
    """That version of the program, or, with none named, the one active on this runtime."""
    found = (
        select(ProgramVersion.id, ProgramVersion.version, Program.name)
        .join(Program, Program.id == ProgramVersion.program_id)
        .where(Program.id == program_id)
    )
    if version is None:
        found = found.join(Deployment, Deployment.program_version_id == ProgramVersion.id).where(
            Deployment.rrotor_id == runtime_id, Deployment.active.is_(True)
        )
    else:
        found = found.where(ProgramVersion.version == version)
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("That program has no such version on this runtime.", program_id=str(program_id))
    return row


async def send_call(
    conn: AsyncConnection,
    hub: Hub,
    runtime_id: uuid.UUID,
    program_id: uuid.UUID,
    version: int | None,
    function: str,
    inputs: dict[str, Any],
    caller: str,
) -> uuid.UUID:
    """Open a run: its row (running), then `call` down the runtime's link. Answers the run's id."""
    runtime = await _runtime(conn, runtime_id)
    found = await _version(conn, runtime_id, program_id, version)
    values = {"program_version_id": found.id, "rrotor_id": runtime_id, "function": function, "caller": caller}
    run_id = (await conn.execute(insert(Run).values(**values, status=RUNNING).returning(Run.id))).scalar_one()
    await hold_run(conn, run_id)
    message = Call(
        run_id=run_id, program=found.name, version=found.version, function=function, inputs=inputs, caller=caller
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
    """Deploy, activate or remove one version on a runtime. A program in git gets a one-hour token for its repo, to
    fetch exactly that commit; the rrotor answers `deployed`. Removing it drops its deployment here at once."""
    runtime = await _runtime(conn, runtime_id)
    found = (
        select(ProgramVersion.version, ProgramVersion.commit_sha, Program.name, Program.repo, Program.user_id)
        .join(Program, Program.id == ProgramVersion.program_id)
        .where(ProgramVersion.id == version_id)
    )
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("You have no such program version.", version_id=str(version_id))
    token = None
    if row.repo and action != "remove":
        if github is None:
            raise Unavailable("GitHub isn't set up on this server.", reason="github_off")
        token = (await repo_token(conn, github, row.user_id, row.repo)).token
    if action == "remove":
        gone = delete(Deployment).where(Deployment.rrotor_id == runtime_id, Deployment.program_version_id == version_id)
        await conn.execute(gone)
    message = Deploy(
        type=action, program=row.name, version=row.version, repo=row.repo, commit_sha=row.commit_sha, token=token
    )
    await deliver(hub, runtime, message)
