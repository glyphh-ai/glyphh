"""Migration 0028_one_thing on a database with data: production's baseline brought to 0027, rows put in what 0028
drops, deletes and revokes and in what it keeps, then 0028 run. The lists of what must be gone are the backup's own
(scripts/one-thing-backup.py), so the backup and the migration cannot drift apart."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import schema
from glyphh_server.db.schema import apply_schema
from tests.db.test_migrations import REAL, SETTINGS_HERE, baseline, own  # noqa: F401  (fixtures)

SCRIPT: Path = Path(__file__).resolve().parents[2] / "scripts" / "one-thing-backup.py"
ONE_THING: int = 28

# A person and their org, and one row in each kind of thing 0028 touches. Ids are fixed so the test can name them.
ORG, USER, RROTOR = (f"00000000-0000-0000-0000-00000000000{n}" for n in (1, 2, 3))
BEFORE: str = f"""
INSERT INTO orgs (id, name, plan_version_id) SELECT '{ORG}', 'Kept org', id FROM plan_versions LIMIT 1;
INSERT INTO users (id, org_id, email, role) VALUES ('{USER}', '{ORG}', 'kept@people.test', 'admin');
INSERT INTO rrotors (id, user_id, mode, state, token_hash, name, public_url)
    VALUES ('{RROTOR}', '{USER}', 'self', 'ready', 'rrotor-hash', 'box', 'https://box.example');
INSERT INTO runtime_keys (user_id, rrotor_id, name, key_hash, scope, calls)
    VALUES ('{USER}', '{RROTOR}', 'runtime key', 'hash-runtime', 'runtime', 7);
INSERT INTO runtime_keys (user_id, name, key_hash, scope, clearance) VALUES
    ('{USER}', 'bot x', 'hash-bot', 'cloud', 0),
    ('{USER}', 'my key', 'hash-mine', 'cloud', 0.5),
    ('{USER}', 'bot of mine', 'hash-cleared', 'cloud', 1);
INSERT INTO bots (org_id, slug, name, model) VALUES ('{ORG}', 'x', 'X', 'claude');
INSERT INTO connections (org_id, app, app_name, account_id) VALUES ('{ORG}', 'slack', 'Slack', 'apn_1');
INSERT INTO licenses (id, org_id, tier, cluster_sync_enabled, issued_at, expires_at, customer_id, key)
    VALUES (gen_random_uuid(), '{ORG}', 'pro', true, now(), now(), 'cus_1', 'signed');
INSERT INTO org_sso (org_id, issuer, client_id, client_secret, reviewers)
    VALUES ('{ORG}', 'https://idp.example', 'client', 'sealed', '{{reviewers}}');
"""


def _backup_lists() -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """The tables the backup saves whole, and the columns it saves from tables that stay."""
    spec = importlib.util.spec_from_file_location("one_thing_backup", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TABLES, {name: gone for name, (_, gone) in module.COLUMNS.items()}


async def _all(conn: AsyncConnection, sql: str) -> list[tuple[object, ...]]:
    return [tuple(r) for r in await conn.execute(text(sql))]


@pytest.fixture
async def at_0027(baseline: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    """The baseline with every migration before 0028 run, and the rows above; the folder 0028 is then added to."""
    for n, path in REAL:
        if n < ONE_THING:
            (tmp_path / path.name).write_text(path.read_text())
    monkeypatch.setattr(schema, "MIGRATIONS", tmp_path)
    await apply_schema(baseline, SETTINGS_HERE)
    async with baseline.begin() as conn:
        await schema.run_sql(conn, BEFORE)
    return tmp_path


async def test_0028_drops_what_is_not_adas_and_keeps_every_person_and_their_keys(
    baseline: AsyncEngine,  # noqa: F811
    at_0027: Path,
) -> None:
    tables, columns = _backup_lists()
    keys = "SELECT name, key_hash, revoked_at IS NOT NULL FROM runtime_keys ORDER BY name"
    async with baseline.connect() as conn:
        assert len(await _all(conn, keys)) == 4
        assert await _all(conn, "SELECT count(*) FROM bots") == [(1,)]
    path = dict(REAL)[ONE_THING]
    (at_0027 / path.name).write_text(path.read_text())
    await apply_schema(baseline, SETTINGS_HERE)
    await apply_schema(baseline, SETTINGS_HERE)  # and again: recorded, so not run twice
    async with baseline.connect() as conn:
        left = {t for (t,) in await _all(conn, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        assert left.isdisjoint(tables) and {"orgs", "users", "runtime_keys", "plan_versions", "org_sso"} <= left
        has = "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        have = set(await _all(conn, has))
        assert not [(t, c) for t, gone in columns.items() for c in gone if (t, c) in have]
        assert await _all(conn, keys) == [  # the runtime's key deleted; the bot's revoked; a person's own untouched
            ("bot of mine", "hash-cleared", False),
            ("bot x", "hash-bot", True),
            ("my key", "hash-mine", False),
        ]
        assert await _all(conn, "SELECT DISTINCT scope FROM runtime_keys") == [("cloud",)]
        assert await _all(conn, f"SELECT name FROM orgs WHERE id = '{ORG}'") == [("Kept org",)]
        assert await _all(conn, f"SELECT email, role FROM users WHERE id = '{USER}'") == [("kept@people.test", "admin")]
        assert await _all(conn, "SELECT issuer FROM org_sso") == [("https://idp.example",)]


async def test_0028_can_be_run_again_on_a_database_that_has_had_it(
    baseline: AsyncEngine,  # noqa: F811
    at_0027: Path,
) -> None:
    sql = dict(REAL)[ONE_THING].read_text()
    async with baseline.begin() as conn:
        await schema.run_sql(conn, sql)
        await schema.run_sql(conn, sql)
    async with baseline.connect() as conn:
        assert await _all(conn, "SELECT name FROM runtime_keys WHERE revoked_at IS NULL ORDER BY name") == [
            ("bot of mine",),
            ("my key",),
        ]
