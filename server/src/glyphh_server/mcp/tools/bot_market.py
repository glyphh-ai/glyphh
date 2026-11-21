"""The bots marketplace through the connector (docs/specs/bots.md, 9): bot templates Glyphh ships, searched and read,
and one copied into the org as its own bot."""

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.mcp.tools.bots import line
from glyphh_server.ops.bots import templates


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(None, max_length=200, description="Words its name, summary or apps have")


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=80, description="The template's slug (bot_templates lists them)")


class Install(Slug):
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name in the org; the template's")


def _line(t: templates.BotTemplate) -> str:
    return f"{t.name} ({t.slug}): {t.summary}; needs {', '.join(t.apps) or 'no connection'}"


async def search(ctx: Context, args: Search) -> Done:
    found = templates.listing(args.q)
    return Done("\n".join(_line(t) for t in found.templates) or "No such bot template.", dump(found))


async def read(ctx: Context, args: Slug) -> Done:
    t = templates.one(args.slug)
    return Done(f"{_line(t)}.\n{t.description}\nTools: {', '.join(t.tools)}", dump(t))


async def install(ctx: Context, args: Install) -> Done:
    given = templates.InstallIn(name=args.name)
    bot = await templates.install(ctx.conn, ctx.who, ctx.settings.secret_key, args.slug, given)
    return Done(f"Added {line(bot)}. bot_run runs it.", dump(bot))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "bot_templates",
        "Bots marketplace",
        "Bot templates Glyphh ships, ready to add to the org: what each does and the connections it needs.",
        Search,
        search,
        True,
    ),
    Tool("bot_template", "A bot template", "One bot template: what it does, its tools and gates.", Slug, read, True),
    Tool(
        "bot_template_install",
        "Add a bot from the marketplace",
        "Copy a bot template into the org as its own bot, its tools scoped to the org's connections (connect each app "
        "it needs first: the refusal names them).",
        Install,
        install,
    ),
)
