"""The backup that comes before migration 0028_one_thing: every table that migration drops, every column it drops
from a table that stays, and the API keys it deletes or revokes, written to files. Nothing is changed: one read-only
transaction at one snapshot, so the files agree with each other.

Run it where GLYPHH_DATABASE_URL reaches the database, with asyncpg installed (the server's own image has both):

    python one-thing-backup.py /tmp/one-thing-backup

It writes, in that folder, `<name>.jsonl.gz` (one JSON object per row, as Postgres's row_to_json gives it) and
`<name>.columns.json` (each column's name and type) for every table, `manifest.json` (when, which database, the
newest migration applied, each file's rows and SHA-256), and beside the folder `<folder>.tar.gz` holding all of it.
Every file is read back and its rows counted against the table before it answers; any difference exits 1.

`bot_keys.anthropic_key` (an org's own Anthropic API key, sealed) is left out unless `--with-secrets` is given: a
customer's key to another service is not kept past the feature it was for. Its `hint` (the last four characters) is.

A table or column already gone is recorded in the manifest as absent, not an error, so the script can be run again
after the migration, into another folder, to see that nothing is left. A folder that already exists is refused, so
a backup is never written over."""

import asyncio
import gzip
import hashlib
import json
import os
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

# Dropped whole (0028_one_thing.sql, in the order it drops them).
TABLES: tuple[str, ...] = (
    "run_marks",
    "project_turns",
    "project_runs",
    "projects",
    "program_events",
    "program_runs",
    "programs",
    "bot_decisions",
    "bot_sessions",
    "bot_plugins",
    "bot_runs",
    "bot_keys",
    "bots",
    "connections",
    "template_installs",
    "templates",
    "apps",
    "nodes",
    "licenses",
    "github_installations",
    "mods",
    "rrotors",
)
# Columns dropped from tables that stay: the table, its key, the columns.
COLUMNS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "runtime_keys": (("id",), ("rrotor_id", "calls", "last_used_at")),
    "org_sso": (("org_id",), ("reviewers",)),
    "plan_versions": (
        ("id",),
        ("max_machines", "precedents", "sync", "ha", "offline", "connections", "connection_cents"),
    ),
}
# Rows the migration deletes or revokes in a table that stays: a name for the file, the table, the condition.
ROWS: dict[str, tuple[str, str]] = {
    "runtime_keys_deleted": ("runtime_keys", "scope = 'runtime'"),
    "runtime_keys_revoked": (
        "runtime_keys",
        "scope = 'cloud' AND name LIKE 'bot %' AND clearance = 0 AND revoked_at IS NULL",
    ),
}
SECRET: dict[str, tuple[str, ...]] = {"bot_keys": ("anthropic_key",)}
NEWEST: str = "SELECT coalesce(max(version), -1) FROM schema_migrations"
HAS: str = (
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position"
)


def dsn(url: str) -> str:
    """The server's setting as asyncpg takes it: no SQLAlchemy driver in the scheme, `sslmode` for `ssl`."""
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
    return url.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")


def quoted(names: tuple[str, ...]) -> str:
    return ", ".join(f'"{n}"' for n in names)


async def columns(conn: asyncpg.Connection, table: str) -> list[dict[str, str]]:
    return [{"name": r["column_name"], "type": r["data_type"]} for r in await conn.fetch(HAS, table)]


async def write(conn: asyncpg.Connection, out: Path, name: str, select: str, where: str) -> dict[str, Any]:
    """One file of rows, read back and counted against the table at the same snapshot."""
    path, rows, digest = out / f"{name}.jsonl.gz", 0, hashlib.sha256()
    with gzip.open(path, "wt", encoding="utf-8") as f:
        async for record in conn.cursor(f"SELECT row_to_json(t)::text FROM (SELECT {select} WHERE {where}) t"):
            f.write(record[0] + "\n")
            rows += 1
    digest.update(path.read_bytes())
    with gzip.open(path, "rt", encoding="utf-8") as f:
        read = sum(1 for line in f if json.loads(line) is not None)
    counted = await conn.fetchval(f"SELECT count(*) FROM (SELECT {select} WHERE {where}) t")
    if not rows == read == counted:
        raise SystemExit(f"{name}: wrote {rows} rows, read back {read}, the table holds {counted}")
    return {"file": path.name, "rows": rows, "sha256": digest.hexdigest()}


async def table(conn: asyncpg.Connection, out: Path, name: str, secrets: bool) -> dict[str, Any]:
    cols = await columns(conn, name)
    if not cols:
        return {"absent": True}
    left_out = () if secrets else SECRET.get(name, ())
    kept = tuple(c["name"] for c in cols if c["name"] not in left_out)
    (out / f"{name}.columns.json").write_text(json.dumps(cols, indent=1))
    done = await write(conn, out, name, f'{quoted(kept)} FROM "{name}"', "true")
    return done | ({"left_out": list(left_out)} if left_out else {})


async def dropped_columns(conn: asyncpg.Connection, out: Path, name: str) -> dict[str, Any]:
    key, gone = COLUMNS[name]
    have = {c["name"]: c for c in await columns(conn, name)}
    there = tuple(c for c in gone if c in have)
    if not there:
        return {"absent": True}
    file = f"{name}_columns"
    (out / f"{file}.columns.json").write_text(json.dumps([have[c] for c in (*key, *there)], indent=1))
    return await write(conn, out, file, f'{quoted((*key, *there))} FROM "{name}"', "true")


async def rows(conn: asyncpg.Connection, out: Path, file: str) -> dict[str, Any]:
    name, where = ROWS[file]
    have = {c["name"] for c in await columns(conn, name)}
    if not {"scope", "clearance", "name"} <= have:
        return {"absent": True}
    return await write(conn, out, file, f'* FROM "{name}"', where)


async def backup(url: str, out: Path, secrets: bool) -> dict[str, Any]:
    out.mkdir(parents=True)  # an existing folder is refused: a backup is never written over
    conn = await asyncpg.connect(dsn(url), statement_cache_size=0)  # safe behind a connection pooler too
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            manifest: dict[str, Any] = {
                "taken_at": datetime.now(UTC).isoformat(),
                "database": await conn.fetchval("SELECT current_database()"),
                "newest_migration": await conn.fetchval(NEWEST),
                "tables": {name: await table(conn, out, name, secrets) for name in TABLES},
                "columns": {name: await dropped_columns(conn, out, name) for name in COLUMNS},
                "rows": {file: await rows(conn, out, file) for file in ROWS},
            }
    finally:
        await conn.close()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    with tarfile.open(f"{out}.tar.gz", "w:gz") as tar:
        tar.add(out, arcname=out.name)
    return manifest


def main(argv: list[str]) -> None:
    given = [a for a in argv if not a.startswith("--")]
    if len(given) != 1 or not os.environ.get("GLYPHH_DATABASE_URL"):
        raise SystemExit("usage: GLYPHH_DATABASE_URL=... python one-thing-backup.py <folder> [--with-secrets]")
    out = Path(given[0])
    manifest = asyncio.run(backup(os.environ["GLYPHH_DATABASE_URL"], out, "--with-secrets" in argv))
    for part in ("tables", "columns", "rows"):
        for name, done in manifest[part].items():
            print(f"{part[:-1]:6} {name:24} {'absent' if done.get('absent') else done['rows']}")
    print(f"{out}.tar.gz")


if __name__ == "__main__":
    main(sys.argv[1:])
