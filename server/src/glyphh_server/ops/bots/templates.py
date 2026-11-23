"""The bots marketplace (docs/specs/bot-agent-loop.md, 7): the bot templates Glyphh ships, each a Claude plugin
package (ops/bots/packages.py: library/<slug>/). A template says what the bot does, the apps it needs, what it
decides, its example prompts and where it can run. Installing one makes the org's own bot from the package's sidecar
(its name, cat, instructions, decisions, standing task and examples), scoped to the org's connection of each app it
needs, and keeps the package as the bot's plugin at the version installed. It is refused until every app is
connected (naming the ones missing), and, for a template that runs only on a rrotor, until the org has one linked.
A template with a program (program.py) installs it too, as the org's program done by the new bot. The copy is the
org's: changing it never touches the template."""

import copy
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import botviews, installed, packages, places, store
from glyphh_server.ops.bots import package_parts as parts
from glyphh_server.ops.bots.exposed import ConnectorTool
from glyphh_server.ops.bots.schedule import Schedule
from glyphh_server.ops.bots.shape import Place
from glyphh_server.ops.bots.views import BotIn, BotView, ScopeIn
from glyphh_server.ops.programs import store as programs
from glyphh_server.ops.programs.views import ProgramIn

MISSING: str = "There is no such bot template."
NO_RROTOR: str = "{name} needs a rrotor: it cannot run on Glyphh cloud. Set one up, link it, then install it."


class NeededApp(BaseModel):
    app: str = Field(description="The service, as Pipedream names it (gmail, slack, ...)")
    name: str = Field(description="Its name, for the person")
    tools: list[str] = Field(description="The tools of it the bot uses, by key")


class Decides(BaseModel):
    name: str
    question: str
    outcomes: list[str]


class BotTemplate(BaseModel):
    slug: str
    version: str
    name: str
    summary: str = Field(description="A few plain words on what it does")
    description: str
    look: dict[str, str]
    apps: list[NeededApp] = Field(description="The services it needs a connection to")
    decides: list[Decides] = Field(description="What Ada decides for it, each learned from the person's answers")
    examples: list[str] = Field(description="Things to say to it")
    task: str = Field(description="What it does when it runs on its own")
    schedule: Schedule = Field(description="When the installed bot runs on its own")
    runs_on: list[Place] = Field(description="Where it can run: cloud and rrotor, or rrotor alone")


class BotTemplates(BaseModel):
    templates: list[BotTemplate]


class InstallIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name in the org; the template's")


def _app_name(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", "_").split("_"))


def shown(p: packages.Package) -> BotTemplate:
    side = p.sidecar
    decides = [
        Decides(name=n, question=str(g.get("question") or ""), outcomes=[str(o) for o in g.get("outcomes") or []])
        for n, g in side.decisions.items()
    ]
    return BotTemplate(
        slug=p.slug,
        version=p.version,
        name=side.bot.name,
        summary=side.bot.tagline,
        description=side.bot.description,
        look=side.bot.look,
        apps=[NeededApp(app=r.app, name=_app_name(r.app), tools=r.tools) for r in side.requires],
        decides=decides,
        examples=side.examples,
        task=side.task,
        schedule=Schedule(**side.schedule),
        runs_on=p.runs_on,  # type: ignore[arg-type]
    )


def listing(q: str | None) -> BotTemplates:
    words = (q or "").lower().split()
    every = [shown(p) for p in packages.library().values()]
    found = [
        t for t in every if all(w in f"{t.name} {t.summary} {' '.join(a.app for a in t.apps)}".lower() for w in words)
    ]
    return BotTemplates(templates=found)


def one(slug: str) -> BotTemplate:
    found = packages.library().get(slug)
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return shown(found)


async def _place(conn: AsyncConnection, p: packages.Package, platform: str) -> Any:
    """Where the installed bot runs: Glyphh cloud when the template can, else the org's first linked rrotor."""
    if "cloud" in p.runs_on:
        return None
    linked = [x for x in (await places.listing(conn)).places if x.id is not None and x.linked]
    if not linked:
        said = NO_RROTOR.format(name=p.sidecar.bot.name)
        raise Invalid(said, reason="rrotor", setup_url=f"{platform}/runtimes")
    return linked[0].id


def spec_of(side: packages.Sidecar) -> dict[str, Any]:
    """A bot's spec from a template's sidecar: its decisions, and what it may reach."""
    spec: dict[str, Any] = {"gates": copy.deepcopy(side.decisions)} if side.decisions else {}  # never the library's
    more = {"hosts": side.hosts, "builtins": side.builtins, "limits": dict(side.limits)}
    return spec | {k: v for k, v in more.items() if v}


async def install(
    conn: AsyncConnection, who: Principal, secret: str, slug: str, given: InstallIn, platform: str = ""
) -> BotView:
    """The org's own bot made from the template, its tools scoped to the org's connection of each app, its package
    kept as its plugin. It is given no folders: a template knows no machine, the bot's owner chooses them after."""
    p = packages.library().get(slug)
    if p is None:
        raise NotFound(MISSING, slug=slug)
    side = p.sidecar
    linked: dict[str, Any] = {}
    for c in await conn.execute(select(Connection).order_by(Connection.created_at)):
        linked.setdefault(c.app, c)
    if missing := [r.app for r in side.requires if r.app not in linked]:
        raise Invalid(f"Connect {', '.join(missing)} first: the bot uses it.", reason="connections", apps=missing)
    body = BotIn(
        name=given.name or side.bot.name, summary=side.bot.tagline, look=side.bot.look, model=side.bot.model,
        instructions=side.bot.instructions, spec=spec_of(side), effort=side.bot.effort, task=side.task,
        examples=side.examples, schedule=Schedule(**side.schedule), runs_on=await _place(conn, p, platform),
        connections=[ScopeIn(connection_id=linked[r.app].id, tools=r.tools) for r in side.requires],
        connector_tools=[ConnectorTool.model_validate(t) for t in side.connector_tools], folders=[],
    )  # fmt: skip
    bot = await store.made(conn, who, secret, body)
    await installed.keep(conn, bot, p)
    if parts.PROGRAM in p.files:  # its program, done by the bot, where the bot runs
        made = ProgramIn(name=bot.name, summary=side.bot.tagline, source=p.files[parts.PROGRAM], bot=bot.slug,
                         runs_on=bot.runs_on)  # fmt: skip
        await programs.made(conn, who, made, template=slug)
    return await botviews.view(conn, bot)
