"""The template library's edges: the seed (a template no longer shipped retired, never deleted), two templates adding
the same tool, an install or removal a worker refuses, a removal after a model was deleted by hand, and templates
with Ada Cloud off."""

from typing import Any

import httpx
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.errors import Refused
from glyphh_ada.process import Worker
from glyphh_server.models import Template
from glyphh_server.ops.templates import installs
from glyphh_server.ops.templates.library import SHIPPED, seed_templates
from tests.ada.mcp import data, refused, signed_in, tool
from tests.db.helpers import person

API = "http://api.test"


async def a_copy(engine: AsyncEngine, slug: str) -> None:
    """A template beside Agentic memory that adds the same tools."""
    body = {**SHIPPED[0].model_dump(mode="json"), "slug": slug, "name": "Copycat"}
    async with engine.begin() as conn:
        row = {"slug": slug, "name": "Copycat", "category": "Memory", "summary": "x", "version": 1, "body": body}
        await conn.execute(insert(Template).values(**row, sort=99))


async def test_the_seed_retires_what_is_no_longer_shipped(engine: AsyncEngine) -> None:
    await a_copy(engine, "retired-one")
    async with engine.begin() as conn:
        await seed_templates(conn)
        await seed_templates(conn)
        rows = dict((await conn.execute(select(Template.slug, Template.active))).all())
    assert rows["retired-one"] is False and rows["agentic-memory"] is True


async def test_two_templates_may_not_add_the_same_tool(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    await a_copy(engine, "copycat")
    auth = await signed_in(engine, await person(engine, "Team"))
    await tool(ada, auth, "template_install", slug="agentic-memory")
    clash = await refused(ada, auth, "template_install", slug="copycat")
    assert clash["code"] == "E_CONFLICT" and "glyphh_recall" in clash["tools"]
    async with engine.begin() as conn:
        await conn.execute(Template.__table__.update().where(Template.slug == "copycat").values(active=False))


async def test_a_removal_after_a_model_was_deleted_by_hand(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    auth = await signed_in(engine, await person(engine, "Team"))
    model = data(await tool(ada, auth, "template_install", slug="agentic-memory"))["models"][0]["model"]
    await tool(ada, auth, "ada_model_delete", name=model, confirm=model)
    await tool(ada, auth, "template_remove", slug="agentic-memory", confirm="agentic-memory")


@pytest.mark.parametrize("step", ["install", "remove"])
async def test_a_worker_refusal_is_the_callers(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    auth = await signed_in(engine, await person(engine, "Team"))
    if step == "remove":
        await tool(ada, auth, "template_install", slug="agentic-memory")

    async def refusing(*_: Any) -> Any:
        raise Refused("E_UNAVAILABLE", "Ada is busy.", 503)

    monkeypatch.setattr(installs, "ask", refusing)
    args: dict[str, str] = {"slug": "agentic-memory"} | ({"confirm": "agentic-memory"} if step == "remove" else {})
    assert (await refused(ada, auth, f"template_{step}", **args))["code"] == "E_UNAVAILABLE"


async def test_templates_need_ada_cloud(engine: AsyncEngine, client: httpx.AsyncClient) -> None:
    who = await person(engine, "Team")
    made = await client.post(f"{API}/v1/templates/agentic-memory/install", headers=who.headers)
    assert made.status_code == 503 and made.json()["error"]["reason"] == "ada_off"
    listed = await client.get(f"{API}/v1/templates", headers=who.headers)
    assert listed.json()["templates"][0]["installed"] is False
