"""Tenant isolation: row-level security keyed on the org.

A request made with an install's token, or with a connector access token on /mcp, runs as the role `glyphh_tenant`
with its org in `glyphh.org_id`, and the policies in schema.sql show it only that org's rows: the org, its users,
invites, add-ons and programs, and their identities, installs, tokens, runtimes, GitHub installations, routine
triggers, connector grants, their tokens and OAuth codes, and the programs' versions, deployments, runs, approvals and
events.
Sign-in, the connector's OAuth endpoints (a code or token is found by its hash before anyone is known), Stripe's
webhook and the few operations that cross orgs on purpose (joining another org, being removed from one) run as the
connecting role, which the policies don't bind."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ROLE: str = "glyphh_tenant"


async def enter(conn: AsyncConnection, org_id: object) -> None:
    """From here to the end of the transaction, this connection sees only this org's rows."""
    await conn.execute(text("SELECT set_config('glyphh.org_id', :org, true)"), {"org": str(org_id)})
    await conn.execute(text(f"SET LOCAL ROLE {ROLE}"))


async def leave(conn: AsyncConnection) -> None:
    """Back to the connecting role, for an operation that crosses orgs on purpose."""
    await conn.execute(text("RESET ROLE"))
    await conn.execute(text("SELECT set_config('glyphh.org_id', '', true)"))
