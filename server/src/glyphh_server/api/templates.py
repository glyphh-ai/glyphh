"""The template library (docs/specs/templates.md): browsing it, installing a template for yourself and removing it
(the platform's Templates page), and your glyphh's context for an AI's hooks (the plugin's session-start and prompt
hooks). Installing, removing and the context call Ada's workers, so they sign the caller in on a short transaction of
their own and hold none while a worker answers."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.api.auth import Bearer, Caller, Conn, authenticate
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates import installs, run
from glyphh_server.ops.templates.glyphh import TEXT_MAX
from glyphh_server.ops.templates.installs import TemplateView

router = APIRouter(tags=["templates"])


async def person(request: Request, creds: Bearer) -> Principal:
    """The caller, signed in on a transaction that has ended by the time a worker is asked."""
    async with request.app.state.engine.begin() as conn:
        return await authenticate(conn, creds, request.app.state.settings.mcp_resource)


Person = Annotated[Principal, Depends(person)]


class Asked(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str | None = Field(
        None, max_length=TEXT_MAX, description="What the person just asked; left out, a session's start"
    )


class Context(BaseModel):
    context: str  # "" when the glyphh holds nothing to say


class Library(BaseModel):
    templates: list[TemplateView]


@router.get("/v1/templates", operation_id="listTemplates")
async def list_templates(
    caller: Caller,
    conn: Conn,
    q: Annotated[str | None, Query(max_length=200, description="Matches the name, summary and category")] = None,
) -> Library:
    """The template library, each saying whether you have it installed."""
    return Library(templates=await installs.library(conn, caller, q))


@router.get("/v1/templates/{slug}", operation_id="getTemplate")
async def get_template(slug: str, caller: Caller, conn: Conn) -> TemplateView:
    return await installs.one(conn, caller, slug)


@router.post("/v1/templates/{slug}/install", operation_id="installTemplate")
async def install_template(slug: str, request: Request, who: Person) -> TemplateView:
    """Install a template for yourself: its models made in Ada Cloud as yours, its tools on your connector."""
    state = request.app.state
    return await installs.install(state.ada, state.engine, who, slug)


@router.delete("/v1/templates/{slug}/install", operation_id="removeTemplate")
async def remove_template(slug: str, request: Request, who: Person) -> TemplateView:
    """Remove a template you installed: its models are deleted with everything in them. Not undone."""
    state = request.app.state
    return await installs.remove(state.ada, state.engine, who, slug)


@router.post("/v1/me/glyphh/context", operation_id="glyphhContext")
async def glyphh_context(body: Asked, request: Request, who: Person) -> Context:
    """What your installed templates put before an AI: with no prompt, a session's start (your personality and rules);
    with one, what bears on it."""
    state: Any = request.app.state
    bodies = await installs.installed_by(state.engine, who)
    return Context(context=await run.context(state.ada, who, bodies, body.prompt) if bodies else "")
