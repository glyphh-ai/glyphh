"""Pull requests settled by the server itself, through GitHub's API (docs/specs/bots.md, 10). Review at the end
(`review: end`): the run has a branch of its own (`project-<slug>-<stamp>`, made off the base as it starts), every
turn starts from it and is merged into it as it opens, and when the run is over one pull request of it all, into the
base, waits for the person: merged, the run is done; rejected (closed) or not mergeable, it is failed, saying so. A
run that merged nothing opens none. And a turn's pull request of a run on Glyphh cloud, merged or closed here (a
rrotor's run has its rrotor do it)."""

from typing import Any

from glyphh_server.errors import GlyphhError
from glyphh_server.ops.bots.runs import now

REJECTED: str = "The run's pull request was rejected."
TITLE_MAX: int = 120


def work_branch(slug: str, stamp: str) -> str:
    return f"project-{slug}-{stamp}"


async def begin(svc: Any, run: Any) -> None:
    """The run's own branch, made off the base."""
    repo = await svc.repo_of(run)
    await repo.branch(run.work_branch, await repo.head(run.base_branch))


def _words(run: Any, taken: list[Any]) -> tuple[str, str]:
    task = run.task.strip().splitlines()[0] if run.task.strip() else "the crew's work"
    merged = [f"- #{t.number} {t.title}" for t in taken if t.status == "merged"]
    return f"{run.project_name}: {task}"[:TITLE_MAX], "The crew's merged turns:\n" + "\n".join(merged)


async def finish(svc: Any, run: Any, taken: list[Any], why: str) -> None:
    """The run is over (`why`): done, or with review end its pull request opened and waiting for the person."""
    if run.review != "end" or not run.work_branch:
        await svc.end(run.org_id, run.id, "done", ended=why)
        return
    try:
        repo = await svc.repo_of(run)
        if not any(t.status == "merged" for t in taken):
            await repo.drop(run.work_branch)
            await svc.end(run.org_id, run.id, "done", ended=why)
            return
        pr = await repo.open(run.work_branch, run.base_branch, *_words(run, taken))
    except GlyphhError as err:
        await svc.end(run.org_id, run.id, "failed", err.message)
        return
    await svc.put_run(run.org_id, run.id, status="needs_input", ended=why, pr_url=pr["url"], number=pr["number"])


async def answer(svc: Any, run: Any, said: str) -> None:
    """The whole run's pull request, merged or rejected by the person."""
    repo = await svc.repo_of(run)
    if said == "reject":
        await repo.close(run.number)
        await repo.drop(run.work_branch)
        await svc.end(run.org_id, run.id, "failed", REJECTED)
        return
    merged, why = await repo.merge(run.number, f"Merge PR #{run.number}: {run.project_name}")
    if not merged:
        await svc.end(run.org_id, run.id, "failed", f"The run's pull request did not merge: {why}. It stays open.")
        return
    await repo.drop(run.work_branch)
    await svc.end(run.org_id, run.id, "done")


async def settle(svc: Any, run: Any, turn: Any, said: str) -> None:
    """A turn's pull request of a run on Glyphh cloud: merged (or left open on a conflict, saying why), or closed."""
    repo = await svc.repo_of(run)
    values = {"status": "rejected", "error": ""}
    if said == "merge":
        merged, why = await repo.merge(turn.number, f"Merge PR #{turn.number}: {turn.title}")
        values = {"status": "merged" if merged else "conflict", "error": "" if merged else why}
    else:
        await repo.close(turn.number)
    if values["status"] != "conflict":
        await repo.drop(turn.branch)
    await svc.put_turn(run.org_id, turn.id, **values, finished_at=now())
