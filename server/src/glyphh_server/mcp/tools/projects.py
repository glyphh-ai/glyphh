"""The org's projects (docs/specs/bots.md, 10): a crew of its bots, in no order, on one GitHub repo and a set of
instructions, on Glyphh cloud or one of its rrotors, each turn a pull request; made, read, changed, deleted, run, its
pull request merged or rejected, its run cancelled. GitHub is reached through the Glyphh GitHub App, installed on the
repo in the browser (the platform's Connect GitHub); there is no token to give. The tools that start or move a run
make their own transactions (DETACHED). Projects were swarms: each tool is still called by its old name (WAS), never
listed."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.projects import runs, store
from glyphh_server.ops.projects.views import ProjectIn, ProjectPatch, ProjectRunView, ProjectView, ReviewIn, TaskIn

SLUG = Field(min_length=1, max_length=80, description="The project's slug (projects lists them)")
MODES: dict[str, str] = {"wait": "wait your turn", "orchestrator": "an orchestrator picks"}
REVIEWS: dict[str, str] = {"each_turn": "each turn", "end": "at the end"}


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG


class Update(ProjectPatch):
    slug: str = SLUG


class Task(TaskIn):
    slug: str = SLUG


class RunId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


class Review(ReviewIn):
    run_id: uuid.UUID


def line(p: ProjectView) -> str:
    crew = ", ".join(m.name for m in p.members) or "no bots"
    where = f"rrotor {p.runs_on}" if p.runs_on else "Glyphh cloud"
    return (
        f"{p.name} ({p.slug}): {p.repo_url} on {p.base_branch}, crew {crew}; on {where}, {MODES[p.turn_mode]}, "
        f"review {REVIEWS[p.review]}, at most {p.max_turns} turns"
    )


def run_line(r: ProjectRunView) -> str:
    said = [f"turn {t.n} {t.bot_name}: {t.status}" + (f" {t.pr_url}" if t.pr_url else "") for t in r.turns]
    whole = f" Its pull request: {r.pr_url}." if r.pr_url else ""
    ended = f" ({r.error or r.ended})" if r.error or r.ended else ""
    return f"Run {r.id} of {r.project_slug}: {r.status}{ended}.{whole} " + "; ".join(said)


async def list_projects(ctx: Context, _: NoArgs) -> Done:
    found = await store.listing(ctx.conn)
    said = "\n".join(line(p) for p in found) or "The org has no projects yet."
    return Done(said, {"projects": [dump(p) for p in found]})


async def get_project(ctx: Context, args: Slug) -> Done:
    found = await store.one(ctx.conn, args.slug)
    return Done(line(found), dump(found))


async def create(ctx: Context, args: ProjectIn) -> Done:
    made = await store.create(ctx.conn, ctx.who, args)
    return Done(f"Made {line(made)}. project_run runs it.", dump(made))


async def update(ctx: Context, args: Update) -> Done:
    given = ProjectPatch(**args.model_dump(exclude={"slug"}, exclude_unset=True))
    changed = await store.patch(ctx.conn, args.slug, given)
    return Done(f"Changed {line(changed)}.", dump(changed))


async def delete(ctx: Context, args: Slug) -> Done:
    await store.remove(ctx.conn, args.slug)
    return Done(f"Deleted {args.slug} and its runs.", {"deleted": args.slug})


async def run(ctx: Context, args: Task) -> Done:
    made = await ctx.bots.projects.start(ctx.who, args.slug, args.task, args.model, args.effort)
    return Done(f"{run_line(made)}\nproject_run_get follows it.", dump(made))


async def list_runs(ctx: Context, args: Slug) -> Done:
    found = await runs.listing(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": [dump(r) for r in found]})


async def get_run(ctx: Context, args: RunId) -> Done:
    found = await runs.get(ctx.conn, args.run_id)
    return Done(run_line(found), dump(found))


async def answer(ctx: Context, args: Review) -> Done:
    found = await ctx.bots.projects.answer(ctx.who, args.run_id, args.answer)
    return Done(f"{run_line(found)}\nproject_run_get follows it.", dump(found))


async def cancel(ctx: Context, args: RunId) -> Done:
    found = await ctx.bots.projects.cancel(ctx.who, args.run_id)
    return Done(f"Run {found.id} cancelled.", dump(found))


def _tool(name: str, title: str, about: str, args: type[BaseModel], handler: object, read_only: bool) -> Tool:
    return Tool(name, title, about, args, handler, read_only)  # type: ignore[arg-type]


CREATE: str = (
    "Make a project: a name, its GitHub repo (https://github.com/<owner>/<name>) and base branch, its crew (the "
    "org's bot ids, in no order), its instructions (given here; a file in the repo, PROJECT.md unless "
    "instructions_path says another, is read on every turn too), turn_mode (wait: one bot at a time, whoever has "
    "waited longest and has something to do; orchestrator: a bot of the crew, or Claude, reads the repo and names "
    "the next bot), review (each_turn: each pull request waits for a merge or a no; end: one pull request of the "
    "whole run at its end) and runs_on: none for Glyphh cloud, or one of the org's rrotors (bot_places). Glyphh "
    "cloud has fewer tools than a rrotor: bots read and change files and open pull requests, but run no commands, "
    "tests or browser. There are no rounds: a run goes until the crew or the orchestrator says it is done, or "
    "max_turns or max_spend_cents is reached. Glyphh's GitHub App must be installed on the repo, by a person who "
    "can push to it (Connect GitHub on the platform): a run says so, with the link, when it is not."
)
TOOLS: tuple[Tool, ...] = (
    _tool(
        "projects",
        "Projects",
        "The org's projects: crews of its bots working on a GitHub repo from a set of instructions.",
        NoArgs,
        list_projects,
        True,
    ),
    _tool(
        "project", "A project", "One project: its crew, repo, instructions, turns and review.", Slug, get_project, True
    ),
    _tool("project_create", "Make a project", CREATE, ProjectIn, create, False),
    _tool(
        "project_update",
        "Change a project",
        "Change what is given of a project; its slug stays.",
        Update,
        update,
        False,
    ),
    _tool("project_delete", "Delete a project", "Delete a project and its runs. Not undone.", Slug, delete, False),
    _tool(
        "project_run",
        "Run a project",
        "Run a project, on a task or (none given) on its instructions alone: one bot at a time does its part on a "
        "branch and opens a pull request; with review each_turn, each waits in bot_approvals until "
        "project_run_answer merges or rejects it.",
        Task,
        run,
        False,
    ),
    _tool(
        "project_runs",
        "A project's runs",
        "A project's runs with their turns, the newest first.",
        Slug,
        list_runs,
        True,
    ),
    _tool(
        "project_run_get",
        "A project run",
        "One run: its turns, pull requests, what each bot said.",
        RunId,
        get_run,
        True,
    ),
    _tool(
        "project_run_answer",
        "Merge or reject",
        "The pull request a project run waits on, merged or rejected: a turn's (then the next turn), or the run's.",
        Review,
        answer,
        False,
    ),
    _tool(
        "project_run_cancel",
        "Cancel a project run",
        "End a project run (an open pull request stays).",
        RunId,
        cancel,
        False,
    ),
)
DETACHED: frozenset[str] = frozenset({"project_run", "project_run_answer", "project_run_cancel"})
WAS: dict[str, str] = {"swarms": "projects", "swarm": "project"} | {
    t.name.replace("project_", "swarm_", 1): t.name for t in TOOLS if t.name.startswith("project_")
}
