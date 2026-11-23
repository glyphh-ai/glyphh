"""Migration 0026 and the conversion on a database that holds data (docs/specs/bot-agent-loop.md, 9): production's
baseline brought to the migration before, given orgs, bots that are loops of steps, a run that waits and a project,
then brought forward by the schema step. It ends in schema.sql's shape; every org has its one orchestrator, every
loop bot is an agent with its spec as it was kept, the run that waited is failed, and the new tables are each
org's own. Run again, nothing changes."""

import json
import logging
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import schema, tenancy
from glyphh_server.db.schema import apply_schema, migrations, run_sql
from glyphh_server.models import Bot, BotPlugin, BotRun, BotSession, Project
from tests.db.test_migrations import SETTINGS_HERE, _recorded, _shape, baseline, own  # noqa: F401 (fixtures)

BEFORE: int = 25  # the migrations a database had before bots became agents
OLD: Path = Path(__file__).parent.parent / "bots" / "old_library"
OWN: dict[str, Any] = {"loop": [{"id": "say", "agent": "Say hello."}], "takes": "a name"}


@pytest.fixture
def said() -> Iterator[list[str]]:
    """What the schema step logged."""
    lines: list[str] = []

    class Kept(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    handler = Kept()
    schema.log.addHandler(handler)
    yield lines
    schema.log.removeHandler(handler)


async def _one(conn: AsyncConnection, sql: str, **values: Any) -> Any:
    return (await conn.execute(text(sql), values)).scalar_one()


async def _org(conn: AsyncConnection, name: str, slug: str, spec: dict[str, Any], instructions: str) -> uuid.UUID:
    """An org as it was, with one loop bot and a project (written as SQL: the models know columns it has not yet)."""
    plan = await _one(conn, "INSERT INTO plans (name) VALUES (:n) RETURNING id", n=f"Plan of {name}")
    version = await _one(conn, "INSERT INTO plan_versions (plan_id, version) VALUES (:p, 1) RETURNING id", p=plan)
    org: uuid.UUID = await _one(
        conn, "INSERT INTO orgs (name, plan_version_id) VALUES (:n, :v) RETURNING id", n=name, v=version
    )
    made = "INSERT INTO bots (org_id, slug, name, model, instructions, spec) "
    made += "VALUES (:o, :s, :n, 'claude-sonnet-5-5', :i, CAST(:spec AS jsonb)) RETURNING id"
    bot = await _one(conn, made, o=org, s=slug, n=name, i=instructions, spec=json.dumps(spec))
    waits = "INSERT INTO bot_runs (org_id, bot_id, status, question) VALUES (:o, :b, 'needs_input', CAST(:q AS jsonb))"
    await conn.execute(text(waits), {"o": org, "b": bot, "q": json.dumps({"question": "Yes?", "options": ["yes"]})})
    site = "INSERT INTO projects (org_id, slug, name, repo_url) VALUES (:o, 'site', 'Site', 'https://github.com/a/b')"
    await conn.execute(text(site), {"o": org})
    return org


@pytest.fixture
async def kept(baseline: AsyncEngine) -> tuple[AsyncEngine, uuid.UUID, uuid.UUID]:  # noqa: F811
    """A database at migration 0025 with two orgs: one with Inbox Triage from the library then, one with a bot its
    person wrote."""
    was = json.loads((OLD / "inbox-triage.json").read_text("utf-8"))
    async with baseline.begin() as conn:
        await run_sql(conn, schema.LEDGER)
        await schema._record(conn, 0, "baseline")
        for version, path in migrations(schema.MIGRATIONS)[:BEFORE]:
            await run_sql(conn, path.read_text())
            await schema._record(conn, version, path.stem)
        # a table schema.sql made then (no migration makes it), which 0026 does not change: its statement, as it is
        projects = re.search(r"CREATE TABLE IF NOT EXISTS projects \(.*?\n\);", schema.SCHEMA.read_text(), re.S)
        assert projects is not None
        await run_sql(conn, projects.group(0))
        acme = await _org(conn, "Acme", "inbox-triage", was["spec"], was["instructions"])
        other = await _org(conn, "Other", "hello", OWN, "You say hello.")
    return baseline, acme, other


async def test_a_database_with_loop_bots_is_brought_to_schema_sql_and_its_bots_converted(
    engine: AsyncEngine, kept: tuple[AsyncEngine, uuid.UUID, uuid.UUID], said: list[str]
) -> None:
    eng, acme, other = kept
    assert (await _recorded(eng))[-1][0] == BEFORE
    await apply_schema(eng, SETTINGS_HERE)
    assert await _shape(eng) == await _shape(engine)
    assert (26, "0026_bot_agent_loop") in await _recorded(eng)
    assert "migrated: 0026_bot_agent_loop.sql" in said and "converted: {'orchestrators': 2, 'bots': 2}" in said
    async with eng.connect() as conn:
        bots = {(b.org_id, b.role): b for b in await conn.execute(select(Bot))}
        plugins = list(await conn.execute(select(BotPlugin)))
        runs = list(await conn.execute(select(BotRun)))
        projects = {p.org_id: p.orchestrator for p in await conn.execute(select(Project))}
    assert set(bots) == {(acme, "bot"), (acme, "orchestrator"), (other, "bot"), (other, "orchestrator")}
    triage, hello = bots[acme, "bot"], bots[other, "bot"]
    assert "loop" in triage.old_spec and "loop" not in triage.spec and sorted(triage.spec["gates"]) == ["worth"]
    assert triage.task.startswith("Read my unread mail") and len(triage.examples) == 3 and triage.skills == {}
    assert triage.instructions.startswith("You are Inbox Triage. Your job:")
    assert [(p.org_id, p.bot_id, p.name, p.source) for p in plugins] == [
        (acme, triage.id, "inbox-triage", "template:inbox-triage")
    ]
    assert hello.old_spec == OWN and hello.spec == {} and hello.task == "Do your job now."
    assert "1. Say hello." in hello.skills["how-it-works"] and hello.instructions == "You say hello."
    assert bots[acme, "orchestrator"].slug == "orchestrator" and bots[acme, "orchestrator"].old_spec is None
    assert projects == {acme: bots[acme, "orchestrator"].id, other: bots[other, "orchestrator"].id}
    assert [(r.status, r.question, r.session_id) for r in runs] == [("failed", {}, "")] * 2
    assert all(r.error == "The bot was updated while this run waited: run it again." for r in runs)
    del said[:]
    before = await _rows(eng)
    await apply_schema(eng, SETTINGS_HERE)  # run again at the next deploy: nothing to migrate or convert
    assert await _rows(eng) == before and not [line for line in said if "converted" in line or "migrated" in line]


async def _rows(eng: AsyncEngine) -> list[Any]:
    async with eng.connect() as conn:
        found: list[Any] = []
        for table in (Bot, BotPlugin, BotRun, Project):
            found += [tuple(r) for r in await conn.execute(select(table).order_by(table.id))]
    return found


async def test_an_org_has_one_orchestrator_and_the_new_tables_are_each_orgs_own(
    kept: tuple[AsyncEngine, uuid.UUID, uuid.UUID],
) -> None:
    eng, acme, other = kept
    await apply_schema(eng, SETTINGS_HERE)
    second = {"org_id": acme, "slug": "second", "name": "Second", "model": "claude-sonnet-5-5"}
    with pytest.raises(IntegrityError, match="bots_one_orchestrator"):
        async with eng.begin() as conn:
            await conn.execute(insert(Bot).values(**second, role="orchestrator"))
    with pytest.raises(IntegrityError, match="bots_role"):
        async with eng.begin() as conn:
            await conn.execute(insert(Bot).values(**second, role="boss"))
    async with eng.begin() as conn:
        run = (await conn.execute(select(BotRun.id).where(BotRun.org_id == acme))).scalar_one()
        line = {"org_id": acme, "run_id": run, "session_id": "s1", "entry": {"type": "user"}}
        await conn.execute(insert(BotSession).values(**line))
    async with eng.begin() as conn:
        await tenancy.enter(conn, other)
        assert list(await conn.execute(select(BotPlugin))) == [] and list(await conn.execute(select(BotSession))) == []
        await tenancy.enter(conn, acme)
        assert [p.name for p in await conn.execute(select(BotPlugin))] == ["inbox-triage"]
        assert [(s.session_id, s.subpath, s.entry) for s in await conn.execute(select(BotSession))] == [
            ("s1", "", {"type": "user"})
        ]
    for table, values in (
        (BotSession, line),
        (BotPlugin, {"org_id": acme, "name": "x", "version": "1", "source": "x"}),
    ):
        with pytest.raises(DBAPIError, match="row-level security"):
            async with eng.begin() as conn:
                await tenancy.enter(conn, other)
                bot = (await conn.execute(select(Bot.id))).scalars().first()
                await conn.execute(insert(table).values(**values | ({"bot_id": bot} if table is BotPlugin else {})))
