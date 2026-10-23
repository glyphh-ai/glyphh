"""Enterprise, granted by Glyphh's staff, never bought: the org's plan becomes Enterprise until a date and its own
Stripe subscription (the deal's annual price, invoiced; with hosting on, the metered hosting price too) recorded, and
with hosting on its markup on Fly's rates, so its hosting is reported to that subscription's customer. Revoking it,
or the date passing, puts the org back on Free, its hosted machines stopped and held (ops/held.py), the hosting due
reported first to the subscription it is leaving (ops/billing/meter.py), as a subscription's own change is. A grant
issues the org a licence key through its last day (air-gapped: the contract's term, delivered out of band too);
revoking or ending it revokes the org's keys. Run on the server's machine (`fly ssh console`), where
GLYPHH_LICENSE_SIGNING_KEY is set:

    python -m glyphh_server.ops.enterprise grant --org <uuid> --until <YYYY-MM-DD> --subscription <sub_…> [--markup N]
    python -m glyphh_server.ops.enterprise revoke --org <uuid>"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.seed import ENTERPRISE, FREE
from glyphh_server.errors import Conflict, GlyphhError, NotFound
from glyphh_server.models import BILLING_STATUSES, Org
from glyphh_server.ops import license_keys
from glyphh_server.ops.billing.meter import report
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.held import hold
from glyphh_server.ops.license import load_key
from glyphh_server.ops.plans import newest_version

log = logging.getLogger("glyphh.billing")

CLEARED: dict[str, Any] = {"plan_until": None, "markup_pct": None, "stripe_subscription_id": None, "renews_at": None}


async def _org(conn: AsyncConnection, org_id: uuid.UUID) -> Any:
    found = select(Org.id, Org.name, Org.stripe_subscription_id, Org.plan_until).where(Org.id == org_id)
    found = found.with_for_update()
    org = (await conn.execute(found)).first()
    if org is None:
        raise NotFound("There is no such org.", org_id=str(org_id))
    return org


async def grant(
    engine: AsyncEngine,
    stripe: StripeClient,
    org_id: uuid.UUID,
    until: date,
    markup: int | None,
    subscription: str,
    signing_key: Ed25519PrivateKey,
) -> str:
    """The org on Enterprise through the end of `until` (UTC), at this markup (none: its hosting is not charged),
    billed on this subscription, with a licence key to then. Granted again, a deal renewed or changed (a new
    subscription too, and a new key); a self-serve subscription is cancelled first."""
    sub = await stripe.subscription(subscription)
    async with engine.begin() as conn:
        org = await _org(conn, org_id)
        if org.plan_until is None and org.stripe_subscription_id not in (None, subscription):
            raise Conflict(f"Cancel the org's subscription {org.stripe_subscription_id} first.", reason="subscribed")
        ends = datetime.combine(until + timedelta(days=1), time(), UTC)
        # Its first payment is a paid conversion (the staff view).
        paid = func.coalesce(Org.first_paid_at, func.now()) if sub["status"] == "active" else Org.first_paid_at
        values = {
            "plan_version_id": (await newest_version(conn, ENTERPRISE)).id,
            "plan_until": ends,
            "markup_pct": markup,
            "stripe_subscription_id": subscription,
            "stripe_customer_id": sub["customer"],
            "billing_status": sub["status"] if sub["status"] in BILLING_STATUSES else "none",
            "first_paid_at": paid,
        }
        await conn.execute(update(Org).where(Org.id == org_id).values(**values))
        await license_keys.issue(conn, signing_key, org_id, ends)
    at = "" if markup is None else f", at {markup}%"
    return f"{org.name} is on Enterprise through {until}{at}, billed on {subscription} ({sub['customer']})."


async def back_to_free(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    free = await newest_version(conn, FREE)
    values = CLEARED | {"plan_version_id": free.id, "billing_status": "none"}
    await conn.execute(update(Org).where(Org.id == org_id).values(**values))
    await license_keys.revoke(conn, org_id)


async def revoke(engine: AsyncEngine, org_id: uuid.UUID, fly: Fly | None, stripe: StripeClient | None = None) -> str:
    """The org back on Free; with Stripe, the hosting due reported first to its subscription; its hosted machines
    stopped and held there (with hosting on), kept until deleted. Its Stripe subscription is cancelled in Stripe."""
    if stripe is not None:
        await report(engine, stripe, only=org_id)
    async with engine.begin() as conn:
        org = await _org(conn, org_id)
        await back_to_free(conn, org_id)
        stopped = [] if fly is None else await hold(conn, fly, org_id)
    return f"{org.name} is on Free, {len(stopped)} hosted machines stopped. Cancel its subscription in Stripe."


async def expire(engine: AsyncEngine, stripe: StripeClient | None = None) -> list[uuid.UUID]:
    """Every grant whose date has passed: with Stripe, the hosting due reported first to its subscription; then the
    org back on Free (the tick then holds its machines)."""
    async with engine.connect() as conn:  # the connecting role: every org's
        lapsed = list((await conn.execute(select(Org.id).where(Org.plan_until <= datetime.now(UTC)))).scalars())
    if stripe is not None:
        for org_id in lapsed:
            await report(engine, stripe, only=org_id)  # its own transactions: it locks the org's row itself
    async with engine.begin() as conn:
        ended = select(Org.id).where(Org.id.in_(lapsed), Org.plan_until <= datetime.now(UTC)).with_for_update()
        orgs = list((await conn.execute(ended)).scalars())
        for org_id in orgs:
            await back_to_free(conn, org_id)
            log.info("enterprise ended", extra={"org": str(org_id)})
    return orgs


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="python -m glyphh_server.ops.enterprise", description="Grant or revoke Enterprise."
    )
    commands = cli.add_subparsers(dest="command", required=True)
    granting = commands.add_parser("grant", help="The org on Enterprise until a date")
    granting.add_argument("--org", type=uuid.UUID, required=True)
    granting.add_argument("--until", type=date.fromisoformat, required=True, help="YYYY-MM-DD, the last day")
    granting.add_argument("--markup", type=int, help="With hosting on: percent over Fly's rates, 0 or more")
    granting.add_argument("--subscription", required=True, help="The deal's Stripe subscription, sub_…")
    revoking = commands.add_parser("revoke", help="The org back on Free")
    revoking.add_argument("--org", type=uuid.UUID, required=True)
    return cli


async def run(argv: list[str], settings: Settings, http: httpx.AsyncClient | None = None) -> str:
    args = parser().parse_args(argv)
    if args.command == "grant" and args.markup is not None and args.markup < 0:
        parser().error("--markup is 0 or more")
    engine = make_engine(settings.database_url)
    client = http or httpx.AsyncClient(timeout=10)
    try:
        if args.command == "revoke":
            fly = Fly(client, settings) if settings.hosting_on else None
            meter = settings.stripe_secret_key and StripeClient(
                client, settings.stripe_secret_key, settings.stripe_meter_hosting
            )
            return await revoke(engine, args.org, fly, meter or None)
        stripe = StripeClient(client, settings.stripe_secret_key)
        signing_key = load_key(settings)
        return await grant(engine, stripe, args.org, args.until, args.markup, args.subscription, signing_key)
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
