"""Enterprise, granted by Glyphh's staff, never bought: the org's plan becomes Enterprise until a date, its markup on
Fly's rates and its own Stripe subscription (the deal's annual price, invoiced, and the metered hosting price) recorded,
so its hosting is reported to that subscription's customer. Revoking it, or the date passing, puts the org back on
Free. Run on the server's machine (`fly ssh console`):

    python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --markup <pct> --subscription <sub_…>
    python -m glyphh_server.ops.enterprise revoke --org <uuid>"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.seed import ENTERPRISE, FREE
from glyphh_server.errors import Conflict, GlyphhError, NotFound
from glyphh_server.models import BILLING_STATUSES, Org
from glyphh_server.ops import limits
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.plans import newest_version

log = logging.getLogger("glyphh.billing")

CLEARED: dict[str, Any] = {"plan_until": None, "markup_pct": None, "stripe_subscription_id": None, "renews_at": None}


async def _org(conn: AsyncConnection, org_id: uuid.UUID) -> Any:
    found = select(Org.id, Org.name, Org.stripe_subscription_id).where(Org.id == org_id).with_for_update()
    org = (await conn.execute(found)).first()
    if org is None:
        raise NotFound("There is no such org.", org_id=str(org_id))
    return org


async def grant(
    engine: AsyncEngine, stripe: StripeClient, org_id: uuid.UUID, until: date, markup: int, subscription: str
) -> str:
    """The org on Enterprise through the end of `until` (UTC), at this markup, billed on this subscription."""
    sub = await stripe.subscription(subscription)
    async with engine.begin() as conn:
        org = await _org(conn, org_id)
        if org.stripe_subscription_id not in (None, subscription):
            raise Conflict(f"Cancel the org's subscription {org.stripe_subscription_id} first.", reason="subscribed")
        values = {
            "plan_version_id": (await newest_version(conn, ENTERPRISE)).id,
            "plan_until": datetime.combine(until + timedelta(days=1), time(), UTC),
            "markup_pct": markup,
            "stripe_subscription_id": subscription,
            "stripe_customer_id": sub["customer"],
            "billing_status": sub["status"] if sub["status"] in BILLING_STATUSES else "none",
        }
        await conn.execute(update(Org).where(Org.id == org_id).values(**values))
    return f"{org.name} is on Enterprise through {until}, at {markup}%, billed on {subscription} ({sub['customer']})."


async def back_to_free(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    free = await newest_version(conn, FREE)
    values = CLEARED | {"plan_version_id": free.id, "billing_status": "none"}
    await conn.execute(update(Org).where(Org.id == org_id).values(**values))


async def revoke(engine: AsyncEngine, org_id: uuid.UUID) -> str:
    """The org back on Free, once it has no hosted machines; its Stripe subscription is cancelled in Stripe."""
    async with engine.begin() as conn:
        org = await _org(conn, org_id)
        if await limits.org_machines(conn, org_id):
            raise Conflict("Its hosted machines are deleted first.", reason="machines")
        await back_to_free(conn, org_id)
    return f"{org.name} is on Free. Cancel its subscription in Stripe."


async def expire(engine: AsyncEngine) -> list[uuid.UUID]:
    """Every grant whose date has passed: the org back on Free (any hosted machines left are logged)."""
    async with engine.begin() as conn:  # the connecting role: every org's
        ended = select(Org.id).where(Org.plan_until <= datetime.now(UTC)).with_for_update()
        orgs = list((await conn.execute(ended)).scalars())
        for org_id in orgs:
            await back_to_free(conn, org_id)
            if await limits.org_machines(conn, org_id):
                log.warning("enterprise ended with hosted machines", extra={"org": str(org_id)})
    return orgs


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="python -m glyphh_server.ops.enterprise", description="Grant or revoke Enterprise."
    )
    commands = cli.add_subparsers(dest="command", required=True)
    granting = commands.add_parser("grant", help="The org on Enterprise until a date")
    granting.add_argument("--org", type=uuid.UUID, required=True)
    granting.add_argument("--until", type=date.fromisoformat, required=True, help="YYYY-MM-DD, the last day")
    granting.add_argument("--markup", type=int, required=True, help="Percent over Fly's rates, 0 or more")
    granting.add_argument("--subscription", required=True, help="The deal's Stripe subscription, sub_…")
    revoking = commands.add_parser("revoke", help="The org back on Free")
    revoking.add_argument("--org", type=uuid.UUID, required=True)
    return cli


async def run(argv: list[str], settings: Settings, http: httpx.AsyncClient | None = None) -> str:
    args = parser().parse_args(argv)
    if args.command == "grant" and args.markup < 0:
        parser().error("--markup is 0 or more")
    engine = make_engine(settings.database_url)
    client = http or httpx.AsyncClient(timeout=10)
    try:
        if args.command == "revoke":
            return await revoke(engine, args.org)
        stripe = StripeClient(client, settings.stripe_secret_key)
        return await grant(engine, stripe, args.org, args.until, args.markup, args.subscription)
    finally:
        await client.aclose()
        await engine.dispose()


def main() -> None:
    try:
        print(asyncio.run(run(sys.argv[1:], get_settings())))
    except GlyphhError as err:
        raise SystemExit(f"Refused: {err.message}") from err


if __name__ == "__main__":
    main()
