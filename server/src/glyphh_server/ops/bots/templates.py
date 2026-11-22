"""The bots marketplace (docs/specs/bots.md, 9): bot templates Glyphh ships (library/*.json, read once), each a bot
ready to copy into an org: its instructions, model, spec, skills, and the apps and tools it needs. Installing one makes
the org's own bot from it, scoped to the org's connection of each app it needs (one is refused until every app is
connected, naming the ones missing). The copy is the org's: changing it never touches the template."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import store
from glyphh_server.ops.bots.exposed import ABOUT as TOOLS_ABOUT
from glyphh_server.ops.bots.exposed import ConnectorTool
from glyphh_server.ops.bots.views import BotIn, BotView, ScopeIn

LIBRARY: Path = Path(__file__).with_name("library")
MISSING: str = "There is no such bot template."


class BotTemplate(BaseModel):
    slug: str
    name: str
    summary: str
    description: str
    look: dict[str, str]
    model: str
    instructions: str
    skills: dict[str, str]
    spec: dict[str, Any]
    apps: list[str] = Field(description="The services it needs a connection to (Pipedream app slugs)")
    tools: list[str] = Field(description="The tools it uses, by key")
    connector_tools: list[ConnectorTool] = Field(default_factory=list, description=TOOLS_ABOUT)
    gates: list[str] = Field(default_factory=list, description="Its gates, each its own Ada model that learns")


class BotTemplates(BaseModel):
    templates: list[BotTemplate]


class InstallIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name in the org; the template's")


@cache
def library() -> dict[str, BotTemplate]:
    made = [BotTemplate.model_validate(json.loads(p.read_text())) for p in sorted(LIBRARY.glob("*.json"))]
    return {t.slug: t.model_copy(update={"gates": list(t.spec.get("gates") or {})}) for t in made}


def listing(q: str | None) -> BotTemplates:
    words = (q or "").lower().split()
    found = [
        t for t in library().values() if all(w in f"{t.name} {t.summary} {' '.join(t.apps)}".lower() for w in words)
    ]
    return BotTemplates(templates=found)


def one(slug: str) -> BotTemplate:
    found = library().get(slug)
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def install(conn: AsyncConnection, who: Principal, secret: str, slug: str, given: InstallIn) -> BotView:
    """The org's own bot made from the template, its tools scoped to the org's connection of each app."""
    t = one(slug)
    linked: dict[str, Any] = {}
    for c in await conn.execute(select(Connection).order_by(Connection.created_at)):
        linked.setdefault(c.app, c)
    if missing := [a for a in t.apps if a not in linked]:
        raise Invalid(f"Connect {', '.join(missing)} first: the bot uses it.", reason="connections", apps=missing)
    scopes = [
        ScopeIn(connection_id=linked[a].id, tools=[k for k in t.tools if k.split("-", 1)[0] == a] or t.tools)
        for a in t.apps
    ]
    body = BotIn(
        name=given.name or t.name, summary=t.summary, look=t.look, instructions=t.instructions, model=t.model,
        spec=t.spec, skills=t.skills, connections=scopes, connector_tools=t.connector_tools,
    )  # fmt: skip
    return await store.create(conn, who, secret, body)
