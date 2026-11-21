"""The org's hosted Glyphh bots (docs/specs/bots.md): making one (a name, a cat, instructions, the Claude model and the
Ada models it may ask), scoping the tools it may use per connection, running it, and reading its runs. bot_run waits
on no one but makes its run on a transaction of its own (registry.DETACHED)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.bots import prices, runs, store
from glyphh_server.ops.bots.views import BotIn, BotPatch, BotView, RunView, ScopeIn, ScopesIn

SLUG = Field(min_length=1, max_length=80, description="The bot's slug (bots lists them)")


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG


class Update(BotPatch):
    slug: str = SLUG


class Scopes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    connections: list[ScopeIn] = Field(max_length=50, description="Per connection, the tool keys it may use")


class RunArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    input: str = Field("", max_length=200_000, description="What the bot is given to work on")


class RunId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


def line(bot: BotView) -> str:
    tools = sum(len(c.tools) for c in bot.connections)
    last = f", last run {bot.last_run.status}" if bot.last_run else ""
    return f"{bot.name} ({bot.slug}): {bot.summary or 'no summary'}; {bot.model}, {tools} tools{last}"


def run_line(run: RunView) -> str:
    cost = f"${run.cost_micros / 1_000_000:,.4f}"
    said = run.error or run.output[:300]
    return f"Run {run.id} of {run.bot_slug}: {run.status}, {len(run.steps)} steps, {cost} charged. {said}".strip()


async def list_bots(ctx: Context, _: NoArgs) -> Done:
    found = await store.listing(ctx.conn)
    return Done("\n".join(line(b) for b in found) or "The org has no bots yet.", {"bots": [dump(b) for b in found]})


async def get_bot(ctx: Context, args: Slug) -> Done:
    bot = await store.one(ctx.conn, args.slug)
    return Done(line(bot), dump(bot))


async def create(ctx: Context, args: BotIn) -> Done:
    bot = await store.create(ctx.conn, ctx.who, args)
    return Done(f"Made {line(bot)}. bot_connections_set lets it use tools.", dump(bot))


async def update(ctx: Context, args: Update) -> Done:
    bot = await store.patch(ctx.conn, args.slug, BotPatch(**args.model_dump(exclude={"slug"}, exclude_unset=True)))
    return Done(f"Changed {line(bot)}.", dump(bot))


async def delete(ctx: Context, args: Slug) -> Done:
    await store.remove(ctx.conn, args.slug)
    return Done(f"Deleted {args.slug} and its runs.", {"deleted": args.slug})


async def set_connections(ctx: Context, args: Scopes) -> Done:
    bot = await store.set_scopes(ctx.conn, args.slug, ScopesIn(connections=args.connections))
    return Done(f"{line(bot)}.", dump(bot))


async def models(ctx: Context, _: NoArgs) -> Done:
    found = prices.listing()
    lines = [
        f"{m.id}: ${m.input_cents_per_mtok / 100:g}/${m.output_cents_per_mtok / 100:g} per Mtok" for m in found.models
    ]
    return Done("\n".join(lines), dump(found))


async def run(ctx: Context, args: RunArgs) -> Done:
    made = await ctx.bots.start(ctx.who, args.slug, args.input)
    return Done(f"Run {made.id} queued: bot_run_get follows it.", dump(made))


async def list_runs(ctx: Context, args: Slug) -> Done:
    found = await runs.listing(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": [dump(r) for r in found]})


async def get_run(ctx: Context, args: RunId) -> Done:
    found = await runs.get(ctx.conn, args.run_id)
    return Done(run_line(found), dump(found))


def _tool(name: str, title: str, about: str, args: type[BaseModel], handler: object, read_only: bool) -> Tool:
    return Tool(name, title, about, args, handler, read_only)  # type: ignore[arg-type]


TOOLS: tuple[Tool, ...] = (
    _tool(
        "bots",
        "Bots",
        "The org's Glyphh bots: Claude agents that do a job with the org's connections.",
        NoArgs,
        list_bots,
        True,
    ),
    _tool("bot", "A bot", "One bot: its look, instructions, models, tools and latest run.", Slug, get_bot, True),
    _tool(
        "bot_create",
        "Make a bot",
        "Make a Glyphh bot: a name, a summary, its cat (look: head, tail, eye, extra, accessory, pose), what it does "
        "(instructions), the Claude model it runs on (bot_models) and the Ada models it may ask and teach.",
        BotIn,
        create,
        False,
    ),
    _tool(
        "bot_update",
        "Change a bot",
        "Change what is given of a bot; a new name changes its slug.",
        Update,
        update,
        False,
    ),
    _tool("bot_delete", "Delete a bot", "Delete a bot and its runs. Not undone.", Slug, delete, False),
    _tool(
        "bot_connections_set",
        "Scope a bot's tools",
        "The connections a bot may use and, per connection, which of its tools (connection_tools lists their keys): "
        "the whole list, replacing what it had.",
        Scopes,
        set_connections,
        False,
    ),
    _tool("bot_models", "Bot models", "The Claude models a bot may run on, at their rates.", NoArgs, models, True),
    _tool(
        "bot_run",
        "Run a bot",
        "Run a bot on an input, in the background; its tokens are drawn from the plan's allowance, then the balance.",
        RunArgs,
        run,
        False,
    ),
    _tool("bot_runs", "A bot's runs", "A bot's runs, the newest first.", Slug, list_runs, True),
    _tool("bot_run_get", "A bot run", "One run: its status, steps, answer and cost.", RunId, get_run, True),
)
DETACHED: frozenset[str] = frozenset({"bot_run"})
