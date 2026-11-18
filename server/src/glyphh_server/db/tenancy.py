"""Tenant isolation: row-level security keyed on the org.

A request made with an access token has its org in `glyphh.org_id` for its transaction, and the policies in
schema.sql show it only that org's rows: the org, its users, invites and money records, and their identities,
grants, tokens and OAuth codes. The policies bind the connecting role itself, so no role of its own is needed (a
managed Postgres lets none be made). Sign-in, the OAuth endpoints (a code or token is found by its hash before
anyone is known), Stripe's webhook and the staff view, which crosses orgs on purpose (api/admin/deps.py), run with
no org set, and see every row."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def enter(conn: AsyncConnection, org_id: object) -> None:
    """From here to the end of the transaction, this connection sees only this org's rows."""
    await conn.execute(text("SELECT set_config('glyphh.org_id', :org, true)"), {"org": str(org_id)})


async def leave(conn: AsyncConnection) -> None:
    """No org again, for an operation that crosses orgs on purpose."""
    await conn.execute(text("SELECT set_config('glyphh.org_id', '', true)"))
