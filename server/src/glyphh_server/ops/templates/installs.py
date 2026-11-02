"""Templates as a person sees them, and installing and removing one for themselves (docs/specs/templates.md): an
install makes the template's models in Ada Cloud, named as theirs (ops/templates/glyphh.model_name), then records the
install; a removal deletes those models and every precedent in them, then the install. Each step's database work is a
short transaction of its own, never held while a worker answers. A model already there (an install made again after
one that failed half way) is kept as it is."""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_ada.errors import Refused
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Template, TemplateInstall
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates.ada import ask
from glyphh_server.ops.templates.glyphh import model_name
from glyphh_server.ops.templates.library import Body

MISSING: str = "There is no such template in the library."


class TemplateView(BaseModel):
    slug: str
    name: str
    category: str
    summary: str
    version: int
    models: list[dict[str, str]]  # {key, title, about, model}: model, the name it has (or would have) for this person
    tools: list[dict[str, str]]  # {name, title, description}
    instructions: str
    installed: bool
    installed_version: int | None = None


def view(body: Body, who: Principal, installed: int | None) -> TemplateView:
    models = [{**m.model_dump(), "model": model_name(who.user_id, body.slug, m.key)} for m in body.models]
    tools = [{"name": t.name, "title": t.title, "description": t.description} for t in body.tools]
    return TemplateView(
        **body.model_dump(include={"slug", "name", "category", "summary", "version", "instructions"}),
        models=models,
        tools=tools,
        installed=installed is not None,
        installed_version=installed,
    )


async def _installed(conn: AsyncConnection, who: Principal) -> dict[str, int]:
    rows = await conn.execute(
        select(TemplateInstall.slug, TemplateInstall.version).where(TemplateInstall.user_id == who.user_id)
    )
    return {slug: version for slug, version in rows}


async def library(conn: AsyncConnection, who: Principal, q: str | None = None) -> list[TemplateView]:
    """Every active template, in the library's order, each saying whether this person has it."""
    mine = await _installed(conn, who)
    found = select(Template.body).where(Template.active).order_by(Template.sort, Template.slug)
    if q:
        like = f"%{q}%"
        found = found.where(Template.name.ilike(like) | Template.summary.ilike(like) | Template.category.ilike(like))
    return [view(b, who, mine.get(b.slug)) for b in map(Body.model_validate, (await conn.execute(found)).scalars())]


async def one(conn: AsyncConnection, who: Principal, slug: str) -> TemplateView:
    body = (await conn.execute(select(Template.body).where(Template.slug == slug))).scalar_one_or_none()
    if body is None:
        raise NotFound(MISSING, slug=slug)
    return view(Body.model_validate(body), who, (await _installed(conn, who)).get(slug))


async def installed(conn: AsyncConnection, who: Principal) -> list[Body]:
    """The templates this person has installed, each as the library holds it now."""
    rows = await conn.execute(
        select(Template.body)
        .join(TemplateInstall, TemplateInstall.slug == Template.slug)
        .where(TemplateInstall.user_id == who.user_id)
        .order_by(Template.sort, Template.slug)
    )
    return [Body.model_validate(b) for b in rows.scalars()]


async def installed_by(engine: AsyncEngine, who: Principal) -> list[Body]:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await installed(conn, who)


def _clash(body: Body, others: list[Body]) -> None:
    taken = {t.name: o.name for o in others if o.slug != body.slug for t in o.tools}
    clashes = sorted(t.name for t in body.tools if t.name in taken)
    if clashes:
        raise Conflict(f"{body.name} adds tools you have from another template: {', '.join(clashes)}.", tools=clashes)


async def _make(state: Any, who: Principal, body: Body) -> None:
    for part in body.models:
        name = model_name(who.user_id, body.slug, part.key)
        try:
            await ask(state, who, name, "create", {"spec": {**body.spec, "name": part.key}})
        except Refused as err:
            if err.code != "E_CONFLICT":
                raise


async def install(state: Any, engine: AsyncEngine, who: Principal, slug: str) -> TemplateView:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        raw = (
            await conn.execute(select(Template.body).where(Template.slug == slug, Template.active))
        ).scalar_one_or_none()
        if raw is None:
            raise NotFound(MISSING, slug=slug)
        body = Body.model_validate(raw)
        _clash(body, await installed(conn, who))
    await _make(state, who, body)
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        row = {"org_id": who.org_id, "user_id": who.user_id, "slug": slug, "version": body.version}
        await conn.execute(
            upsert(TemplateInstall)
            .values(**row)
            .on_conflict_do_update(index_elements=["user_id", "slug"], set_={"version": body.version})
        )
    return view(body, who, body.version)


async def remove(state: Any, engine: AsyncEngine, who: Principal, slug: str) -> TemplateView:
    """Delete the template's models of this person, every precedent in them, then the install."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        mine = {b.slug: b for b in await installed(conn, who)}
    body = mine.get(slug)
    if body is None:
        raise NotFound("You have not installed that template.", slug=slug)
    for part in body.models:
        try:
            await ask(state, who, model_name(who.user_id, slug, part.key), "delete", {})
        except Refused as err:
            if err.code != "E_MODEL_MISSING":
                raise
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        await conn.execute(
            delete(TemplateInstall).where(TemplateInstall.user_id == who.user_id, TemplateInstall.slug == slug)
        )
    return view(body, who, None)
