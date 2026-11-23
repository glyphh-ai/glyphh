"""The org's hosted Glyphh bots (docs/specs/bots.md, bot-agent-loop.md): how one is written (bot_guide), and making
one (a Claude agent a person talks to: its instructions, standing task and examples, what Ada decides for it, its
notes, a look, the Claude model, per connection its tools), reading, changing and deleting it. The org's
orchestrator is one of them, listed first: changed like any bot, never deleted. Its runs are bot_runs.py's."""

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.bots import places, prices, store, voices
from glyphh_server.ops.bots.guide import GUIDE
from glyphh_server.ops.bots.views import BotIn, BotPatch, BotView, ScopeIn, ScopesIn

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


def line(bot: BotView) -> str:
    decides = ", ".join(bot.spec.get("gates") or {}) or "nothing"
    role = ", the orchestrator (never deleted)" if bot.role == "orchestrator" else ""
    last = f", last run {bot.last_run.status}" if bot.last_run else ""
    when = f"schedule {bot.schedule_summary}" + (f", Next run {bot.next_run}" if bot.next_run else "")
    where = f"runs on rrotor {bot.runs_on}" if bot.runs_on else "runs on Glyphh cloud"
    may = "; ".join(f"{f.path} ({'read and change' if f.access == 'write' else 'read only'})" for f in bot.folders)
    folders = f"; folders: {may}" if may else ""
    model = f"{bot.model} at {bot.effort} effort"
    said = f"{bot.name} ({bot.slug}{role}): {bot.summary or 'no summary'}; decides {decides}; {model}{last}"
    return f"{said}; {when}; {where}{folders}"


async def list_places(ctx: Context, _: NoArgs) -> Done:
    found = await places.listing(ctx.conn)
    shown = [f"{p.name} ({p.mode}{'' if p.linked else ', offline'}): {p.id or 'none'}" for p in found.places]
    return Done("\n".join(shown) + "\n(bot_create and bot_update take the id as runs_on)", dump(found))


async def guide(ctx: Context, _: NoArgs) -> Done:
    return Done(GUIDE, {"guide": GUIDE})


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(None, max_length=200, description="Words its name, slug or summary has: finds a bot to run")


async def list_bots(ctx: Context, args: Search) -> Done:
    found = await store.listing(ctx.conn, args.q)
    return Done("\n".join(line(b) for b in found) or "The org has no bots yet.", {"bots": [dump(b) for b in found]})


async def get_bot(ctx: Context, args: Slug) -> Done:
    bot = await store.one(ctx.conn, args.slug)
    return Done(line(bot), dump(bot))


async def create(ctx: Context, args: BotIn) -> Done:
    bot = await store.create(ctx.conn, ctx.who, ctx.settings.secret_key, args)
    return Done(f"Made {line(bot)}. bot_run runs it.", dump(bot))


async def update(ctx: Context, args: Update) -> Done:
    bot = await store.patch(ctx.conn, args.slug, BotPatch(**args.model_dump(exclude={"slug"}, exclude_unset=True)))
    return Done(f"Changed {line(bot)}.", dump(bot))


async def delete(ctx: Context, args: Slug) -> Done:
    await store.remove(ctx.conn, args.slug, ctx.settings.secret_key)
    return Done(f"Deleted {args.slug} and its runs.", {"deleted": args.slug})


async def set_connections(ctx: Context, args: Scopes) -> Done:
    bot = await store.set_scopes(ctx.conn, args.slug, ScopesIn(connections=args.connections))
    return Done(f"{line(bot)}.", dump(bot))


async def models(ctx: Context, _: NoArgs) -> Done:
    found = prices.listing()
    lines = [
        f"{m.id}: ${m.input_cents_per_mtok / 100:g}/${m.output_cents_per_mtok / 100:g} per Mtok on Glyphh's key, "
        f"${m.own_key_input_cents_per_mtok / 100:g}/${m.own_key_output_cents_per_mtok / 100:g} on the org's own"
        for m in found.models
    ]
    return Done("\n".join(lines) + f"\n(Glyphh's markup: {found.markup_pct}%)", dump(found))


async def list_voices(ctx: Context, _: NoArgs) -> Done:
    found = voices.listing()
    return Done(", ".join(f"{v.id} ({v.accent} {v.gender})" for v in found.voices), dump(found))


def _tool(name: str, title: str, about: str, args: type[BaseModel], handler: object, read_only: bool) -> Tool:
    return Tool(name, title, about, args, handler, read_only)  # type: ignore[arg-type]


TOOLS: tuple[Tool, ...] = (
    _tool("bot_guide", "How bots work", "How a Glyphh bot is written: read it before bot_create.", NoArgs, guide, True),
    _tool(
        "bots",
        "Bots",
        "The org's Glyphh bots, searched by `q`, its orchestrator first: each a Claude agent that does a job with the "
        "org's connections, with Ada deciding what it decides and learning from the person's answers. Each is a "
        "tool to use: bot_run says something to it.",
        Search,
        list_bots,
        True,
    ),
    _tool(
        "bot",
        "A bot",
        "One bot: its instructions, standing task, examples, decisions, notes, tools and latest run.",
        Slug,
        get_bot,
        True,
    ),
    _tool(
        "bot_create",
        "Make a bot",
        "Make a Glyphh bot (bot_guide says how): a name, a summary, its cat (look: head, tail, eye, extra, accessory, "
        "pose) or a drawn mascot (bot_mascot), instructions (who it is and how it works), its task (what it does when "
        "it runs on its own), examples (prompts a person might type), the Claude model (bot_models), its permission "
        "mode (ask, connection or auto: which actions wait for the person's yes), its voice (bot_voices), its spec "
        "(gates: the decisions it can ask Ada about; hosts; limits), skills (its notes) and, per connection, its "
        "tools; its schedule in plain words (every: off, hour, day, weekdays, week, month; at HH:MM, weekday, day, "
        "the person's timezone) and where it runs (runs_on, one of bot_places; none: Glyphh cloud); its effort (how "
        "hard Claude works: low, medium, high, xhigh or max; medium unless said) and, on a rrotor, the folders of "
        "that machine it may use (folders: each {path, access: read or write}; the rrotor refuses one its owner does "
        "not offer). Checked before it is made: every problem is said at once.",
        BotIn,
        create,
        False,
    ),
    _tool(
        "bot_update",
        "Change a bot",
        "Change what is given of a bot (its instructions, task, examples, schedule, where it runs: runs_on null is "
        "Glyphh cloud; its effort; its folders, the whole list, [] for none), checked again; its slug stays.",
        Update,
        update,
        False,
    ),
    _tool(
        "bot_delete",
        "Delete a bot",
        "Delete a bot and its runs. Not undone. The orchestrator is never deleted: it is changed instead.",
        Slug,
        delete,
        False,
    ),
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
    _tool("bot_voices", "Bot voices", "The voices a bot may speak in (its `voice`).", NoArgs, list_voices, True),
    _tool(
        "bot_places",
        "Where bots run",
        "Where a bot can run (its runs_on): Glyphh cloud, then the org's rrotors, each said linked or offline.",
        NoArgs,
        list_places,
        True,
    ),
)
