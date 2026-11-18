"""The wind-down command (`python -m glyphh_server.winddown`) on a throwaway database with production's shape: the
retired products' tables with rows in them, some Ada Cloud schemas, OAuth clients left by the connector, and money
to settle. `counts` reads it right and changes nothing; `drop` leaves exactly the kept tables, the platform's own
client and every user and org; again, it drops nothing; and it refuses without its two flags."""

import ast
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import winddown
from glyphh_server.db.engine import make_engine
from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Base, LlmBalance, OAuthClient, Org, User
from glyphh_server.ops.connector import tokens
from tests.conftest import ADMIN_URL, DATABASE_URL, PLATFORM_ID, SETTINGS, _fresh_database
from tests.db.helpers import RESOURCE, Person, granted, other_client, person
from tests.db.test_migrations import PRODUCTION, as_production

WINDDOWN_DB: str = "glyphh_winddown_test"
HERE = SETTINGS.model_copy(
    update={"database_url": make_url(DATABASE_URL).set(database=WINDDOWN_DB).render_as_string(hide_password=False)}
)
DROP: list[str] = ["drop", "--platform-client-id", str(PLATFORM_ID), "--yes-i-have-a-backup"]
ADA: list[str] = [f"ada_{uuid.uuid4().hex}" for _ in range(3)]
SRC: Path = Path(winddown.__file__).parent


async def _fill(engine: AsyncEngine) -> list[Person]:
    """Three people (one subscribed, one past due and holding a balance), two other clients (one with a grant),
    rows in tables that go, and Ada's schemas (with one schema that only looks like one)."""
    people = [await person(engine) for _ in range(3)]
    claude = await other_client(engine)
    await other_client(engine, "A rrotor")
    await granted(engine, people[0], client_id=claude)
    async with engine.begin() as conn:
        paying = {"billing_status": "active", "stripe_subscription_id": "sub_wd_1", "stripe_customer_id": "cus_wd_1"}
        await conn.execute(update(Org).where(Org.id == people[0].org_id).values(**paying))
        late = {"billing_status": "past_due", "stripe_subscription_id": "sub_wd_2"}
        await conn.execute(update(Org).where(Org.id == people[1].org_id).values(**late))
        await conn.execute(update(Org).where(Org.id == people[2].org_id).values(billing_status="canceled"))
        await conn.execute(insert(LlmBalance).values(org_id=people[1].org_id, micros=12_500_000))
        await conn.execute(insert(LlmBalance).values(org_id=people[2].org_id, micros=0))
        await conn.execute(text("INSERT INTO mods (slug, name, description) VALUES ('ada', 'Ada', 'One row')"))
        usage = "INSERT INTO ada_usage (org_id, period, requests) VALUES (:org, '2026-11', 7)"
        for who in people[:2]:
            await conn.execute(text(usage), {"org": who.org_id})
        for name in [*ADA, "ada_not_an_org"]:
            await conn.execute(text(f'CREATE SCHEMA "{name}"'))
            await conn.execute(text(f'CREATE TABLE "{name}".precedents (id int)'))
    return people


@pytest.fixture
async def old() -> AsyncIterator[tuple[AsyncEngine, list[Person]]]:
    await _fresh_database(make_url(ADMIN_URL).set(database=WINDDOWN_DB).render_as_string(hide_password=False))
    eng = make_engine(HERE.database_url)
    await as_production(eng)
    await apply_schema(eng, HERE)  # as the wound-down server's start does: the plans and the platform's client
    people = await _fill(eng)
    yield eng, people
    await eng.dispose()


async def _run(argv: list[str], settings: object = HERE) -> tuple[int, list[str]]:
    said: list[str] = []
    return await winddown.run(argv, settings, said.append), said  # type: ignore[arg-type]


async def _state(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as conn:
        tables = set((await conn.execute(text(winddown.TABLES))).scalars())
        schemas = set(
            (await conn.execute(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'ada_%'"))).scalars()
        )
        clients = set((await conn.execute(select(OAuthClient.id))).scalars())
        users = set((await conn.execute(select(User.id))).scalars())
        orgs = set((await conn.execute(select(Org.id))).scalars())
    return {"tables": tables, "schemas": schemas, "clients": clients, "users": users, "orgs": orgs}


def _rows(said: list[str]) -> dict[str, tuple[str, str]]:
    return {p[0]: (p[1], p[2]) for p in (line.split() for line in said[1:40]) if len(p) == 3}


async def test_counts_reads_every_table_and_what_is_left_to_settle(old: tuple[AsyncEngine, list[Person]]) -> None:
    engine, _ = old
    before = await _state(engine)
    status, said = await _run(["counts"])
    assert status == 0
    rows = _rows(said)
    assert set(rows) == set(winddown.KEEP) | set(winddown.DROP)
    assert {name for name, (todo, _) in rows.items() if todo == "keep"} == set(winddown.KEEP)
    assert rows["users"] == ("keep", "3") and rows["orgs"] == ("keep", "3") and rows["oauth_clients"] == ("keep", "3")
    assert rows["connector_grants"] == ("keep", "4") and rows["llm_balances"] == ("keep", "2")
    assert rows["mods"] == ("drop", "1") and rows["ada_usage"] == ("drop", "2") and rows["apps"] == ("drop", "0")
    assert said[-6:] == [
        "tables in neither list (left alone; look before dropping): none",
        "ada schemas: 3",
        "orgs with an active or past-due Stripe subscription: 2",
        "orgs holding a Stripe subscription id: 2",
        "prepaid balances above zero: 1, together 12500000 micro-dollars ($12.50)",
        "oauth clients that are not the platform's: 2",
    ]
    assert await _state(engine) == before


async def test_counts_prints_numbers_only(old: tuple[AsyncEngine, list[Person]]) -> None:
    _, people = old
    _, said = await _run(["counts"])
    printed = "\n".join(said)
    for who in people:
        assert who.email not in printed and str(who.user_id) not in printed and str(who.org_id) not in printed
    assert "sub_wd" not in printed and "cus_wd" not in printed and "Ada Lovelace" not in printed


async def test_drop_refuses_without_both_flags_or_the_servers_own_client(old: tuple[AsyncEngine, list[Person]]) -> None:
    engine, _ = old
    before = await _state(engine)
    for argv in (["drop"], DROP[:3], ["drop", "--yes-i-have-a-backup"]):
        assert await _run(argv) == (2, [winddown.NEEDS_BOTH])
    other = str(next(c for c in before["clients"] if c != PLATFORM_ID))  # type: ignore[attr-defined]
    for given, why in ((other, "not this server's GLYPHH_PLATFORM_CLIENT_ID"), ("the-platform", "must be a UUID")):
        status, said = await _run(["drop", "--platform-client-id", given, "--yes-i-have-a-backup"])
        assert status == 2 and why in said[0] and said[0].startswith("Nothing was changed."), said
    unknown = str(uuid.uuid4())  # the server set to a client the database does not have
    status, said = await _run([*DROP[:2], unknown, DROP[3]], HERE.model_copy(update={"platform_client_id": unknown}))
    assert status == 2 and "No oauth_clients row" in said[0]
    assert await _state(engine) == before


async def test_drop_leaves_the_kept_tables_one_client_and_everyone_and_again_drops_nothing(
    old: tuple[AsyncEngine, list[Person]],
) -> None:
    engine, people = old
    before = await _state(engine)
    status, said = await _run(DROP)
    assert status == 0, said
    assert said[:3] == [f"dropped schema {name}" for name in sorted(ADA)]
    assert said[3:-2] == [f"dropped table {name}" for name in winddown.DROP]
    assert said[-2:] == ["deleted 2 oauth clients that were not the platform's, and their grants", "Done."]
    after = await _state(engine)
    assert after["tables"] == set(winddown.KEEP)
    assert after["schemas"] == {"ada_not_an_org"}
    assert after["clients"] == {PLATFORM_ID}
    assert after["users"] == before["users"] and after["orgs"] == before["orgs"] and len(before["users"]) == 3  # type: ignore[arg-type]
    async with engine.begin() as conn:  # the platform's sign-ins go on working
        token = people[0].headers["authorization"].removeprefix("Bearer ")
        assert (await tokens.principal_for(conn, token, RESOURCE)).user_id == people[0].user_id  # type: ignore[union-attr]
    assert await _run(DROP) == (0, ["Nothing to drop: it was all gone already."])
    assert await _state(engine) == after
    await apply_schema(engine, HERE)  # and the next start makes none of it again
    assert (await _state(engine))["tables"] == set(winddown.KEEP)
    _, counted = await _run(["counts"])
    assert _rows(counted)["mods"] == ("drop", "absent") and "ada schemas: 0" in counted


async def test_a_failure_ends_non_zero_with_its_transaction_rolled_back(old: tuple[AsyncEngine, list[Person]]) -> None:
    engine, _ = old
    async with engine.begin() as conn:  # something the list does not know hangs on a table that goes
        await conn.execute(text("CREATE VIEW mods_seen AS SELECT slug FROM mods"))
    before = await _state(engine)
    status, said = await _run(DROP)
    assert status == 1 and said[-1].startswith("Failed, and the transaction it was in was rolled back:"), said
    after = await _state(engine)
    assert after["tables"] == before["tables"] and after["clients"] == before["clients"]  # none of the one transaction
    assert after["schemas"] == {"ada_not_an_org"}  # the schemas went before it, a transaction each
    async with engine.begin() as conn:
        await conn.execute(text("DROP VIEW mods_seen"))
    assert (await _run(DROP))[0] == 0  # run again, it finishes
    assert (await _state(engine))["tables"] == set(winddown.KEEP)


async def test_a_table_in_neither_list_is_named_and_left_alone(old: tuple[AsyncEngine, list[Person]]) -> None:
    engine, _ = old
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE newer_than_the_list (id int)"))
    _, said = await _run(["counts"])
    assert "tables in neither list (left alone; look before dropping): newer_than_the_list" in said
    assert (await _run(DROP))[0] == 0
    assert (await _state(engine))["tables"] == {*winddown.KEEP, "newer_than_the_list"}


def test_every_table_is_kept_or_dropped_and_the_kept_ones_are_the_schemas() -> None:
    made = {
        line.split()[5]
        for line in PRODUCTION.read_text().splitlines()
        if line.startswith("CREATE TABLE IF NOT EXISTS ")
    }
    assert len(made) == 38 and made | {"schema_migrations"} == set(winddown.KEEP) | set(winddown.DROP)
    assert not set(winddown.KEEP) & set(winddown.DROP)
    assert set(winddown.KEEP) == set(Base.metadata.tables) | {"schema_migrations"}


def test_nothing_in_the_server_imports_the_command() -> None:
    """It never runs at import or at boot: no module of the server names it."""
    for path in SRC.rglob("*.py"):
        if path.name != "winddown.py":
            names = [n for node in ast.walk(ast.parse(path.read_text())) for n in _imported(node)]
            assert not [n for n in names if "winddown" in n], path


def _imported(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module or "", *(a.name for a in node.names)]
    return []


async def test_the_command_runs_as_a_module_with_the_apps_own_settings(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import asyncio
    import runpy
    import warnings

    monkeypatch.setattr("sys.argv", ["winddown", "counts"])

    def run() -> int:
        with warnings.catch_warnings(), pytest.raises(SystemExit) as ended:
            warnings.simplefilter("ignore", RuntimeWarning)  # the module is imported already; that's fine here
            runpy.run_module("glyphh_server.winddown", run_name="__main__")
        return int(ended.value.code or 0)

    assert await asyncio.to_thread(run) == 0
    assert "ada schemas: 0" in capsys.readouterr().out
