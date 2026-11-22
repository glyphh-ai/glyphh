"""The org's swarms (docs/specs/bots.md, 10): a crew of its bots taking turns on one GitHub repo on one of its
rrotors, each turn a pull request; made, read, changed, deleted, run on a task, its pull request merged or rejected,
its run cancelled. The org's GitHub token is set on the platform (PUT /v1/github-key), never through the chat. The
tools that send a call to the rrotor make their own transactions (DETACHED)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.swarms import runs, store
from glyphh_server.ops.swarms.views import ReviewIn, SwarmIn, SwarmPatch, SwarmRunView, SwarmView, TaskIn

SLUG = Field(min_length=1, max_length=80, description="The swarm's slug (swarms lists them)")


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG


class Update(SwarmPatch):
    slug: str = SLUG


class Task(TaskIn):
    slug: str = SLUG


class RunId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


class Review(ReviewIn):
    run_id: uuid.UUID


def line(s: SwarmView) -> str:
    crew = ", ".join(m.name for m in s.members) or "no bots"
    return f"{s.name} ({s.slug}): {s.repo_url} on {s.base_branch}, crew {crew}; {s.rounds} rounds, review {s.review}"


def run_line(r: SwarmRunView) -> str:
    said = [f"turn {t.n} {t.bot_name}: {t.status}" + (f" {t.pr_url}" if t.pr_url else "") for t in r.turns]
    return f"Run {r.id} of {r.swarm_slug}: {r.status}{' (' + r.error + ')' if r.error else ''}. " + "; ".join(said)


async def list_swarms(ctx: Context, _: NoArgs) -> Done:
    found = await store.listing(ctx.conn)
    return Done("\n".join(line(s) for s in found) or "The org has no swarms yet.", {"swarms": [dump(s) for s in found]})


async def get_swarm(ctx: Context, args: Slug) -> Done:
    found = await store.one(ctx.conn, args.slug)
    return Done(line(found), dump(found))


async def create(ctx: Context, args: SwarmIn) -> Done:
    made = await store.create(ctx.conn, ctx.who, args)
    return Done(f"Made {line(made)}. swarm_run runs it on a task.", dump(made))


async def update(ctx: Context, args: Update) -> Done:
    changed = await store.patch(
        ctx.conn, args.slug, SwarmPatch(**args.model_dump(exclude={"slug"}, exclude_unset=True))
    )
    return Done(f"Changed {line(changed)}.", dump(changed))


async def delete(ctx: Context, args: Slug) -> Done:
    await store.remove(ctx.conn, args.slug)
    return Done(f"Deleted {args.slug} and its runs.", {"deleted": args.slug})


async def run(ctx: Context, args: Task) -> Done:
    made = await ctx.bots.swarms.start(ctx.who, args.slug, args.task)
    return Done(f"{run_line(made)}\nswarm_run_get follows it.", dump(made))


async def list_runs(ctx: Context, args: Slug) -> Done:
    found = await runs.listing(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": [dump(r) for r in found]})


async def get_run(ctx: Context, args: RunId) -> Done:
    found = await runs.get(ctx.conn, args.run_id)
    return Done(run_line(found), dump(found))


async def answer(ctx: Context, args: Review) -> Done:
    found = await ctx.bots.swarms.answer(ctx.who, args.run_id, args.answer)
    return Done(f"{run_line(found)}\nswarm_run_get follows it.", dump(found))


async def cancel(ctx: Context, args: RunId) -> Done:
    found = await ctx.bots.swarms.cancel(ctx.who, args.run_id)
    return Done(f"Run {found.id} cancelled.", dump(found))


def _tool(name: str, title: str, about: str, args: type[BaseModel], handler: object, read_only: bool) -> Tool:
    return Tool(name, title, about, args, handler, read_only)  # type: ignore[arg-type]


TOOLS: tuple[Tool, ...] = (
    _tool(
        "swarms",
        "Swarms",
        "The org's swarms: crews of its bots taking turns on a GitHub repo.",
        NoArgs,
        list_swarms,
        True,
    ),
    _tool(
        "swarm", "A swarm", "One swarm: its crew in order, repo, base branch, rounds, review.", Slug, get_swarm, True
    ),
    _tool(
        "swarm_create",
        "Make a swarm",
        "Make a swarm: a name, its GitHub repo (https://github.com/<owner>/<name>) and base branch, its crew (the "
        "org's bot ids, in speaking order), rounds, review (each_turn: each pull request waits for a merge or a no; "
        "auto: merged as it opens) and runs_on, one of the org's rrotors (bot_places); the rrotor needs "
        "ANTHROPIC_API_KEY and the org its GitHub token (set on the platform).",
        SwarmIn,
        create,
        False,
    ),
    _tool("swarm_update", "Change a swarm", "Change what is given of a swarm; its slug stays.", Update, update, False),
    _tool("swarm_delete", "Delete a swarm", "Delete a swarm and its runs. Not undone.", Slug, delete, False),
    _tool(
        "swarm_run",
        "Run a swarm",
        "Run a swarm on a task: each bot in turn does its part on a branch and opens a pull request; with review "
        "each_turn, each waits in bot_approvals until swarm_run_answer merges or rejects it.",
        Task,
        run,
        False,
    ),
    _tool("swarm_runs", "A swarm's runs", "A swarm's runs with their turns, the newest first.", Slug, list_runs, True),
    _tool(
        "swarm_run_get", "A swarm run", "One run: its turns, pull requests, what each bot said.", RunId, get_run, True
    ),
    _tool(
        "swarm_run_answer",
        "Merge or reject",
        "The pull request a swarm run waits on, merged or rejected: then the next bot goes.",
        Review,
        answer,
        False,
    ),
    _tool(
        "swarm_run_cancel", "Cancel a swarm run", "End a swarm run (an open pull request stays).", RunId, cancel, False
    ),
)
DETACHED: frozenset[str] = frozenset({"swarm_run", "swarm_run_answer", "swarm_run_cancel"})
