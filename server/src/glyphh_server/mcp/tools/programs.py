"""The org's programs (docs/specs/programs.md, 6): listed, read, made or changed (from program.py or its steps),
deleted and scheduled; and `search_tool`, the tools a bot or a program could use, one added to a bot with `add_to`.
Running one is program_runs.py's."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.errors import NotFound
from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops.bots.schedule import Schedule
from glyphh_server.ops.programs import found, store
from glyphh_server.ops.programs.views import AddToolIn, ProgramIn, ProgramPatch, ProgramView

SLUG = Field(min_length=1, max_length=80, description="The program's slug (programs lists them)")


class Words(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field("", max_length=200, description="Words its name or summary has")


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG


class Save(ProgramPatch):
    slug: str | None = Field(None, max_length=80, description="The program to change; none: make a new one (name)")


class Scheduled(Schedule):
    slug: str = SLUG


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field("", max_length=200, description="Words the tool has: its app, name or what it does")
    bot: str | None = Field(None, max_length=80, description="A bot's slug: whether it has each tool")
    add_to: str | None = Field(None, max_length=80, description="A bot's slug: give it the one tool found")


def line(p: ProgramView) -> str:
    where = f"rrotor {p.runs_on}" if p.runs_on else "Glyphh cloud"
    said = f"{p.slug}: {p.name}, {len(p.flow)} steps on {where}; {p.schedule_summary}"
    return said + (f". It cannot run yet: {'; '.join(p.problems)}" if p.problems else "")


async def listing(ctx: Context, args: Words) -> Done:
    shown = await store.listed(ctx.conn, args.q)
    return Done("\n".join(line(p) for p in shown) or "No programs yet.", {"programs": [dump(p) for p in shown]})


async def get(ctx: Context, args: Slug) -> Done:
    shown = await store.view(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done(f"{line(shown)}\n\n{shown.source}", dump(shown))


async def save(ctx: Context, args: Save) -> Done:
    given = args.model_dump(exclude={"slug"}, exclude_unset=True)
    if args.slug is None:
        shown = await store.create(ctx.conn, ctx.who, ProgramIn(**given))
    else:
        shown = await store.patch(ctx.conn, args.slug, ProgramPatch(**given))
    return Done(f"Saved. {line(shown)}", dump(shown))


async def delete(ctx: Context, args: Slug) -> Done:
    await store.remove(ctx.conn, args.slug)
    return Done(f"Program {args.slug} deleted, with its runs.", {"deleted": args.slug})


async def schedule(ctx: Context, args: Scheduled) -> Done:
    given = Schedule(**args.model_dump(exclude={"slug"}))
    shown = await store.patch(ctx.conn, args.slug, ProgramPatch(schedule=given))
    return Done(f"{shown.slug}: {shown.schedule_summary}; next {shown.next_run or 'never'}.", dump(shown))


def _found_line(t: Any) -> str:
    has = ", the bot has it" if t.added else ""
    return f"{t.app}: {t.title} ({t.key}{', reads only' if t.read_only else ''}{has})"


async def search(ctx: Context, args: Search) -> Done:
    """The tools found; with `add_to` and exactly one found, given to that bot."""
    tools = await found.search(ctx.bots.pd, ctx.bots.engine, ctx.who, args.q, args.add_to or args.bot)
    data: dict[str, Any] = {"tools": [dump(t) for t in tools]}
    if args.add_to is None:
        return Done("\n".join(_found_line(t) for t in tools) or "No tool has those words.", data)
    if len(tools) != 1:
        raise NotFound(f"{len(tools)} tools have those words: name the one to add exactly.", tools=data["tools"])
    pick = tools[0]
    added = AddToolIn(connection_id=pick.connection_id, tool=pick.key)
    await found.add(ctx.bots.pd, ctx.bots.engine, ctx.who, args.add_to, added)
    return Done(f"{args.add_to} can now use {pick.title} ({pick.app}).", data | {"added": pick.key})


TOOLS: tuple[Tool, ...] = (
    Tool("programs", "Programs", "The org's programs: what each does, its steps, where it runs, its schedule.",
         Words, listing, read_only=True),
    Tool("program_get", "A program", "One program: its program.py, its steps (FLOW), its problems, its last run.",
         Slug, get, read_only=True),
    Tool("program_save", "Save a program",
         "Make a program (no slug: name it) or change one: `flow` writes its steps into program.py's FLOW in place, "
         "`source` replaces program.py (not both). Steps: tool (a bot's tool), bot (a task for a bot), ask (the "
         "person), branch (on an earlier result), code (a function of program.py, on a rrotor). A program is kept "
         "even while it cannot run; its problems are said.", Save, save),
    Tool("program_delete", "Delete a program", "A program deleted, with its runs.", Slug, delete, destructive=True),
    Tool("program_schedule", "Schedule a program",
         "When the program runs by itself (every off, hour, day, weekday, week, month), and what each run is given; "
         "every scheduled run is logged like any.", Scheduled, schedule),
    Tool("search_tool", "Find a tool",
         "Find tools a bot or a program could use, among the org's connected apps and Glyphh's built-ins; with "
         "add_to, give the one found to that bot.", Search, search),
)  # fmt: skip
DETACHED: frozenset[str] = frozenset({"search_tool"})
