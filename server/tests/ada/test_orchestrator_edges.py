"""The make, decide and record ops' edges: only the install's own models, a name that is the template's own or too
long, a spec the kernel refuses (not kept as made), the 60-model bound, a worker refusing a model made before, and an
install gone from under a make."""

from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.errors import Refused
from glyphh_ada.process import Worker
from glyphh_server.errors import NotFound
from glyphh_server.models import TemplateInstall
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates import bots
from tests.ada.mcp import data, refused, signed_in, tool
from tests.ada.test_orchestrator import GATE, job
from tests.db.helpers import Person, member, person


def signed(who: Person) -> Principal:
    return Principal(user_id=who.user_id, org_id=who.org_id, role="admin")


async def test_only_the_installs_own_models(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    alice = await person(engine, "Team")
    bob = await member(engine, alice.org_id)
    mine, theirs = await signed_in(engine, alice), await signed_in(engine, bob)
    await tool(ada, mine, "template_install", slug="orchestrator")
    await tool(ada, mine, "template_install", slug="agentic-memory")
    await tool(ada, theirs, "template_install", slug="orchestrator")
    case = job("triage", 3, "drafts")
    for model in (
        "launch-watch",  # never made
        "memory",  # the template's, but not a gate
        f"me-{bob.user_id.hex[:12]}-orchestrator-make_bot",  # someone else's
        f"me-{alice.user_id.hex[:12]}-agentic-memory-memory",  # hers, from another template
    ):
        no = await refused(ada, mine, "glyphh_bot_decide", model=model, data=case)
        assert no["code"] == "E_NOT_FOUND" and no["model"] == model
    no = await refused(ada, mine, "glyphh_bot_record", model="launch-watch", data=case, outcome="make")
    assert no["code"] == "E_NOT_FOUND"


async def test_a_name_it_may_not_make(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    auth = await signed_in(engine, await person(engine, "Team"))
    await tool(ada, auth, "template_install", slug="orchestrator")
    own = await refused(ada, auth, "glyphh_bot_model", name="memory", spec=GATE)
    assert own["code"] == "E_CONFLICT" and own["reason"] == "name"
    long = await refused(ada, auth, "glyphh_bot_model", name="a" * 35, spec=GATE)
    assert long["code"] == "E_INVALID" and long["most"] == 34
    assert (await refused(ada, auth, "glyphh_bot_model", name="Bad_Name", spec=GATE))["code"] == "E_INVALID"
    bad = await refused(ada, auth, "glyphh_bot_model", name="broken", spec={"layers": "no"})
    assert bad["code"] == "E_SPEC"
    no = await refused(ada, auth, "glyphh_bot_decide", model="broken", data={})
    assert no["code"] == "E_NOT_FOUND"  # a model the kernel refused is not kept as made


async def test_at_most_sixty_made(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "template_install", slug="orchestrator")
    async with engine.begin() as conn:
        full = [f"gate-{i}" for i in range(bots.MADE_MAX)]
        await conn.execute(update(TemplateInstall).where(TemplateInstall.user_id == who.user_id).values(made=full))
    over = await refused(ada, auth, "glyphh_bot_model", name="one-more", spec=GATE)
    assert over["code"] == "E_LIMIT" and over["most"] == bots.MADE_MAX
    again = await tool(ada, auth, "glyphh_bot_model", name="gate-0", spec=GATE)  # one it has made: no new room needed
    assert data(again)["made"] is True
    await tool(ada, auth, "template_remove", slug="orchestrator", confirm="orchestrator")  # the 59 never made: missing


async def test_a_worker_refusing_a_made_model_keeps_it(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    await tool(ada, auth, "template_install", slug="orchestrator")
    await tool(ada, auth, "glyphh_bot_model", name="kept", spec=GATE)

    async def refusing(*_: Any) -> Any:
        raise Refused("E_UNAVAILABLE", "Ada is busy.", 503)

    monkeypatch.setattr(bots, "ask", refusing)
    assert (await refused(ada, auth, "glyphh_bot_model", name="kept", spec=GATE))["code"] == "E_UNAVAILABLE"
    assert await bots.made_by(engine, signed(who), "orchestrator") == ["kept"]


async def test_a_make_after_the_install_is_gone(engine: AsyncEngine) -> None:
    who = await person(engine, "Team")
    with pytest.raises(NotFound):
        await bots._keep(engine, signed(who), "orchestrator", "x", True)
