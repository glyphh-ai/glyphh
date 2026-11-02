"""The connector's template tools (docs/specs/templates.md): the library (templates, template), installing and
removing one for yourself, and the tools each template you have installed adds to your own connector, never your
org's (listed by `mine`, called by `call_mine`). Offered while Ada Cloud is on: a template's models live there."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.errors import Conflict
from glyphh_server.mcp.tools.base import Context, Done, Tool
from glyphh_server.ops.templates import installs, run
from glyphh_server.ops.templates.installs import TemplateView
from glyphh_server.ops.templates.library import Body

SLUG = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$", description="The template's slug (templates lists them)")


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(None, max_length=200, description="Matches the name, summary and category")


class Slug(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG


class Removal(Slug):
    confirm: str = Field(description="The slug again: removing deletes its models and everything in them")


def shown(t: TemplateView) -> str:
    have = f", installed (version {t.installed_version})" if t.installed else ""
    return f"{t.slug}: {t.name} ({t.category}, version {t.version}{have}). {t.summary}"


async def library(ctx: Context, args: Search) -> Done:
    found = await installs.library(ctx.conn, ctx.who, args.q)
    text = "\n".join(map(shown, found)) or "No template matches."
    return Done(text, {"templates": [t.model_dump(mode="json") for t in found]})


async def template(ctx: Context, args: Slug) -> Done:
    t = await installs.one(ctx.conn, ctx.who, args.slug)
    adds = "\n".join(f"- {x['name']}: {x['description']}" for x in t.tools)
    return Done(f"{shown(t)}\nTools it adds:\n{adds}", t.model_dump(mode="json"))


async def install(ctx: Context, args: Slug) -> Done:
    t = await installs.install(ctx.ada, ctx.ada.engine, ctx.who, args.slug)
    names = ", ".join(x["name"] for x in t.tools)
    text = f"Installed {t.name}: your connector now has {names} (reconnect it if your AI does not show them yet)."
    return Done(text, t.model_dump(mode="json"))


async def remove(ctx: Context, args: Removal) -> Done:
    if args.confirm != args.slug:
        raise Conflict("Confirm by sending the template's slug as confirm.", reason="confirm", slug=args.slug)
    t = await installs.remove(ctx.ada, ctx.ada.engine, ctx.who, args.slug)
    return Done(f"Removed {t.name} and deleted its models with everything in them.", t.model_dump(mode="json"))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "templates",
        "Templates",
        "The template library: bundles you install for yourself, each adding tools to your own connector over Ada "
        "models of your own (Agentic memory: your glyphh, your memory across every AI you use).",
        Search,
        library,
        True,
    ),
    Tool(
        "template",
        "Template",
        "One template: what it is, the models it makes, the tools it adds.",
        Slug,
        template,
        True,
    ),
    Tool(
        "template_install",
        "Install a template",
        "Install a template for yourself: its models are made in Ada Cloud as yours and its tools are added to your "
        "connector (yours alone, not your org's).",
        Slug,
        install,
    ),
    Tool(
        "template_remove",
        "Remove a template",
        "Remove a template you installed: its tools leave your connector and its models are deleted with everything "
        "in them; confirm repeats the slug. Not undone.",
        Removal,
        remove,
    ),
)
DETACHED: frozenset[str] = frozenset({"template_install", "template_remove"})


def _tool(body: Body, part: Any) -> Tool:
    kinds = ", ".join(body.kinds(part))
    description = f"{part.description} Kinds: {kinds}. From your {body.name} template."

    async def handler(ctx: Context, args: Any) -> Done:
        return Done(*await run.run(ctx.ada, ctx.who, body, part, args))

    return Tool(part.name, part.title, description, run.ARGS[part.op], handler, part.op not in ("remember", "forget"))


def mine(bodies: list[Body]) -> dict[str, Tool]:
    """The tools a person's installed templates add, by name."""
    return {t.name: _tool(b, t) for b in bodies for t in b.tools}
