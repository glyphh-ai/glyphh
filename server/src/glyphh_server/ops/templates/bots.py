"""The ops a template's tools make bots of (docs/specs/templates.md): `make` an Ada model of the person's own from a
spec (a bot's decision), `decide` on one and `record` a precedent in one, over the install's models alone: the
template's (by key) and the ones it made (by name, kept in template_installs.made so a removal deletes them too).
Each is one call to the Ada workers as the person (ops/templates/ada.py); the install's row is read and changed on
short transactions of their own, never held while a worker answers."""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.errors import Refused
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid, LimitReached, NotFound
from glyphh_server.models import TemplateInstall
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates.ada import ask
from glyphh_server.ops.templates.glyphh import mine, model_name
from glyphh_server.ops.templates.library import Body

NAME: str = r"^[a-z][a-z0-9-]{0,40}$"
MADE_MAX: int = 60  # the most models one install makes
LONGEST: int = 63  # an Ada model's name (glyphh_ada.limits.NAME_PATTERN)


async def made_by(engine: AsyncEngine, who: Principal, slug: str) -> list[str]:
    """The names of the models this person's install of a template made, oldest first ([] when not installed)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        found = select(TemplateInstall.made).where(TemplateInstall.user_id == who.user_id, TemplateInstall.slug == slug)
        return list((await conn.execute(found)).scalar_one_or_none() or [])


async def _keep(engine: AsyncEngine, who: Principal, slug: str, name: str, keep: bool) -> bool:
    """Add a name to the install's made models (keep) or take it out, on the row locked: whether it changed."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        mine_ = (TemplateInstall.user_id == who.user_id, TemplateInstall.slug == slug)
        made = (await conn.execute(select(TemplateInstall.made).where(*mine_).with_for_update())).scalar_one_or_none()
        if made is None:
            raise NotFound("You have not installed that template.", slug=slug)
        if (name in made) == keep:
            return False
        if keep and len(made) >= MADE_MAX:
            raise LimitReached(f"A template makes at most {MADE_MAX} models.", limit="made", most=MADE_MAX)
        now = [*made, name] if keep else [m for m in made if m != name]
        await conn.execute(update(TemplateInstall).where(*mine_).values(made=now))
        return True


def _name(user_id: uuid.UUID, body: Body, name: str) -> str:
    if name in {m.key for m in body.models}:
        raise Conflict(f"{name} is one of {body.name}'s own models.", reason="name", name=name)
    full = model_name(user_id, body.slug, name)
    if len(full) > LONGEST:
        most = LONGEST - len(model_name(user_id, body.slug, ""))
        raise Invalid(f"A model's name here is at most {most} characters.", reason="name", most=most)
    return full


async def make(state: Any, who: Principal, body: Body, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    """A new model of the person's from `spec`, checked by the kernel as an install's are; one already there is kept
    as it is and answered."""
    full = _name(who.user_id, body, name)
    added = await _keep(state.engine, who, body.slug, name, True)
    try:
        await ask(state, who, full, "create", {"spec": {**spec, "name": name}})
    except Refused as err:
        if err.code != "E_CONFLICT":
            if added:
                await _keep(state.engine, who, body.slug, name, False)
            raise
        return {"name": name, "model": full, "made": False}
    return {"name": name, "model": full, "made": True}


async def model_of(state: Any, who: Principal, body: Body, kinds: list[str], model: str) -> str:
    """The model asked for, by its key or name (or its whole name), as long as it is this install's."""
    prefix = model_name(who.user_id, body.slug, "")
    short = model.removeprefix(prefix)
    full = model_name(who.user_id, body.slug, short)
    if mine(who.user_id, full) and (short in kinds or short in await made_by(state.engine, who, body.slug)):
        return full
    raise NotFound(f"{model} is not one of your {body.name} models.", model=model)


async def decide(state: Any, who: Principal, body: Body, kinds: list[str], model: str, data: Any) -> dict[str, Any]:
    full = await model_of(state, who, body, kinds, model)
    return {**await ask(state, who, full, "decide", {"data": data}), "model": full}


async def record(
    state: Any, who: Principal, body: Body, kinds: list[str], model: str, data: Any, outcome: str
) -> dict[str, Any]:
    full = await model_of(state, who, body, kinds, model)
    return {**await ask(state, who, full, "record", {"data": data, "outcome": outcome}), "model": full}
