"""The wind-down's clean-up of the database, run by hand inside the app's machine with the app's own database
settings, so no credential leaves it (scripts/wind-down/README.md is the procedure):

    python -m glyphh_server.winddown counts
    python -m glyphh_server.winddown drop --platform-client-id <uuid> --yes-i-have-a-backup

`counts` only reads, and prints numbers only (never an email, a name, a key or a token): the rows of every table,
kept or dropped, how many Ada Cloud schemas there are, and what is left to settle first (live subscriptions, prepaid
balances, OAuth clients that are not the platform's).

`drop` removes the retired products' data: every org's Ada Cloud schema (`ada_<org id>`), one transaction each (all
at once runs Postgres out of lock memory), then, in one transaction, the products' tables in `public` and every
OAuth client but the platform's (its grants, tokens and codes go with a client). It is safe to run again: what is
gone already is skipped, so a second run drops nothing. Any error ends it with a non-zero status, the transaction it
was in rolled back; what earlier transactions dropped stays dropped.

Nothing imports this module and nothing runs it: not the server, the schema step, a deploy or a test of them."""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine

# Every table of the server's database is in one of these two (tests/db/test_winddown.py holds them to the models and
# to production's schema). KEEP is what db/schema.sql makes, and schema_migrations.
KEEP: tuple[str, ...] = (
    "schema_migrations", "orgs", "users", "identities", "invites", "plans", "plan_versions", "oauth_clients",
    "oauth_codes", "connector_grants", "connector_tokens", "admin_audit", "ops_events", "traffic_zones",
    "traffic_days", "traffic_tops", "ada_meter_events", "llm_ledger", "llm_balances",
)  # fmt: skip
# In the order they are dropped: a table before the tables it points at.
DROP: tuple[str, ...] = (
    "ada_model_days", "ada_usage", "llm_usage_days", "template_installs", "templates", "apps", "nodes",
    "runtime_keys", "rrotors", "licenses", "device_codes", "tokens", "installs", "github_installations",
    "sso_domains", "org_sso", "github_traffic_tops", "github_traffic_days", "github_traffic_repos", "mods",
)  # fmt: skip
ADA_SCHEMAS: str = r"SELECT nspname FROM pg_namespace WHERE nspname ~ '^ada_[0-9a-f]{32}$' ORDER BY 1"
TABLES: str = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
LIVE: str = "SELECT count(*) FROM orgs WHERE billing_status IN ('active', 'past_due')"
SUBSCRIBED: str = "SELECT count(*) FROM orgs WHERE stripe_subscription_id IS NOT NULL"
BALANCES: str = "SELECT count(*), coalesce(sum(micros), 0) FROM llm_balances WHERE micros > 0"
OTHER_CLIENTS: str = "SELECT count(*) FROM oauth_clients WHERE id::text <> :platform"
DELETE_OTHERS: str = "DELETE FROM oauth_clients WHERE id::text <> :platform"
NEEDS_BOTH: str = (
    "Nothing was changed. `drop` needs both --platform-client-id <uuid> (the server's GLYPHH_PLATFORM_CLIENT_ID) "
    "and --yes-i-have-a-backup."
)

Say = Callable[[str], None]


class Refused(Exception):
    """The command will not do what was asked; nothing was changed."""


async def _one(conn: AsyncConnection, sql: str, **params: str) -> int:
    return int((await conn.execute(text(sql), params)).scalar_one())


async def _tables(conn: AsyncConnection) -> set[str]:
    return set((await conn.execute(text(TABLES))).scalars())


async def counts(engine: AsyncEngine, settings: Settings, say: Say) -> None:
    """Read only: what the database holds. A table that is not there is `absent`."""
    async with engine.connect() as conn:
        there = await _tables(conn)
        say(f"{'table':<24}{'clean-up':<10}rows")
        for todo, names in (("keep", KEEP), ("drop", DROP)):
            for name in names:
                rows = str(await _one(conn, f'SELECT count(*) FROM public."{name}"')) if name in there else "absent"
                say(f"{name:<24}{todo:<10}{rows}")
        unlisted = sorted(there - set(KEEP) - set(DROP))
        say(f"tables in neither list (left alone; look before dropping): {', '.join(unlisted) or 'none'}")
        say(f"ada schemas: {len(list(await conn.execute(text(ADA_SCHEMAS))))}")
        say(f"orgs with an active or past-due Stripe subscription: {await _one(conn, LIVE)}")
        say(f"orgs holding a Stripe subscription id: {await _one(conn, SUBSCRIBED)}")
        held, micros = (await conn.execute(text(BALANCES))).one()
        say(f"prepaid balances above zero: {held}, together {int(micros)} micro-dollars (${int(micros) / 1e6:,.2f})")
        platform = settings.platform_client_id.strip().lower()
        say(f"oauth clients that are not the platform's: {await _one(conn, OTHER_CLIENTS, platform=platform)}")


async def _platform(engine: AsyncEngine, settings: Settings, given: str) -> uuid.UUID:
    """The platform's client id as given, which must be the one the server itself is set to and a client the
    database has: without it, deleting the others would end every sign-in, staff's included."""
    try:
        client = uuid.UUID(given)
    except ValueError as err:
        raise Refused("Nothing was changed. --platform-client-id must be a UUID.") from err
    if str(client) != settings.platform_client_id.strip().lower():
        raise Refused("Nothing was changed. That is not this server's GLYPHH_PLATFORM_CLIENT_ID.")
    async with engine.connect() as conn:
        if await _one(conn, OTHER_CLIENTS.replace("<>", "="), platform=str(client)) != 1:
            raise Refused("Nothing was changed. No oauth_clients row has that platform client id.")
    return client


async def drop_schemas(engine: AsyncEngine, say: Say) -> int:
    """Every Ada Cloud schema, a transaction each."""
    async with engine.connect() as conn:
        names = list((await conn.execute(text(ADA_SCHEMAS))).scalars())
    for name in names:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        say(f"dropped schema {name}")
    return len(names)


async def drop_tables(engine: AsyncEngine, client: uuid.UUID, say: Say) -> int:
    """The products' tables and the other OAuth clients, in one transaction: all of it or none."""
    done: list[str] = []
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout = '10s'"))  # it gives up rather than queue behind a long one
        there = await _tables(conn)
        for name in (n for n in DROP if n in there):
            await conn.execute(text(f'DROP TABLE public."{name}"'))
            done.append(f"dropped table {name}")
        gone = await conn.execute(text(DELETE_OTHERS), {"platform": str(client)})
        if gone.rowcount:
            done.append(f"deleted {gone.rowcount} oauth clients that were not the platform's, and their grants")
    for line in done:  # said once the transaction is committed
        say(line)
    return len(done)


async def drop(engine: AsyncEngine, settings: Settings, given: str, say: Say) -> None:
    client = await _platform(engine, settings, given)
    changed = await drop_schemas(engine, say) + await drop_tables(engine, client, say)
    say("Done." if changed else "Nothing to drop: it was all gone already.")


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m glyphh_server.winddown", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("counts", help="read only: what the database holds")
    dropping = commands.add_parser("drop", help="remove the retired products' data")
    dropping.add_argument("--platform-client-id", default="")
    dropping.add_argument("--yes-i-have-a-backup", action="store_true")
    return parser.parse_args(argv)


async def run(argv: list[str], settings: Settings, say: Say = print) -> int:
    """The command; answers its exit status."""
    args = _args(argv)
    if args.command == "drop" and not (args.platform_client_id and args.yes_i_have_a_backup):
        say(NEEDS_BOTH)
        return 2
    engine = make_engine(settings.database_url)
    try:
        if args.command == "counts":
            await counts(engine, settings, say)
        else:
            await drop(engine, settings, args.platform_client_id, say)
    except Refused as err:
        say(str(err))
        return 2
    except Exception as err:  # noqa: BLE001  # whatever failed: said, with a failing status
        say(f"Failed, and the transaction it was in was rolled back: {type(err).__name__}: {err}")
        return 1
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run(sys.argv[1:], get_settings())))
