"""Tenant isolation: row-level security keyed on the org.

A request made with an install's token runs as the role `glyphh_tenant` with its org in `glyphh.org_id`, and the
policies below show it only that org's rows: the org, its users, invites and programs, and their identities,
installs, tokens, workspaces, runtimes and connector grants, and the programs' versions, deployments, runs and
approvals. Sign-in, Stripe's webhook and the few operations that cross orgs on purpose (joining another org,
being removed from one) run as the connecting role, which the policies don't bind. Applied on every boot."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ROLE: str = "glyphh_tenant"
ORG: str = "nullif(current_setting('glyphh.org_id', true), '')::uuid"

POLICIES: dict[str, str] = {
    "orgs": f"id = {ORG}",
    "users": f"org_id = {ORG}",
    "invites": f"org_id = {ORG}",
    "identities": "user_id IN (SELECT id FROM users)",
    "installs": "user_id IN (SELECT id FROM users)",
    "workspaces": "user_id IN (SELECT id FROM users)",
    "tokens": "install_id IN (SELECT id FROM installs)",
    "rrotors": "user_id IN (SELECT id FROM users)",
    "connector_grants": "user_id IN (SELECT id FROM users)",
    "programs": f"org_id = {ORG}",
    "program_versions": "program_id IN (SELECT id FROM programs)",
    "deployments": "program_version_id IN (SELECT id FROM program_versions)",
    "runs": "program_version_id IN (SELECT id FROM program_versions)",
    "approvals": "run_id IN (SELECT id FROM runs)",
}

MAKE_ROLE: str = f"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN CREATE ROLE {ROLE} NOLOGIN; END IF;
END $$;
"""


async def apply_tenancy(conn: AsyncConnection) -> None:
    await conn.execute(text(MAKE_ROLE))
    await conn.execute(text(f"GRANT {ROLE} TO current_user"))
    await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {ROLE}"))
    await conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE}"))
    for table, rule in POLICIES.items():
        await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text(f"DROP POLICY IF EXISTS tenant ON {table}"))
        await conn.execute(text(f"CREATE POLICY tenant ON {table} USING ({rule})"))


async def enter(conn: AsyncConnection, org_id: object) -> None:
    """From here to the end of the transaction, this connection sees only this org's rows."""
    await conn.execute(text("SELECT set_config('glyphh.org_id', :org, true)"), {"org": str(org_id)})
    await conn.execute(text(f"SET LOCAL ROLE {ROLE}"))


async def leave(conn: AsyncConnection) -> None:
    """Back to the connecting role, for an operation that crosses orgs on purpose."""
    await conn.execute(text("RESET ROLE"))
    await conn.execute(text("SELECT set_config('glyphh.org_id', '', true)"))
