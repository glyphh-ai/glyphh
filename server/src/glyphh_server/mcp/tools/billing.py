"""Subscribing or changing plan, Stripe's portal, and seats: the admin's, through the existing billing code."""

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import limits
from glyphh_server.ops.billing import changes, checkout


class UpgradeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str = Field(min_length=1, max_length=40, description="The plan's name, as plans lists it")
    seats: int | None = Field(
        default=None, ge=1, le=10_000, description="Seats to subscribe with; defaults to the seats taken"
    )
    addons: list[str] = Field(
        default_factory=list, max_length=20, description="When subscribing: mods to add on, as addons lists them"
    )


class SeatsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seats: int = Field(ge=1, le=10_000)


async def upgrade(ctx: Context, args: UpgradeArgs) -> Done:
    org = await checkout.billing_row(ctx.conn, ctx.who.org_id)
    stripe = ctx.stripe()
    if org.stripe_subscription_id is not None:
        changed = await changes.change_plan(ctx.conn, ctx.who, stripe, args.plan)
        return Done(f"Your org is on {changed.plan.name} now, prorated.", {"org": dump(changed)})
    seats = args.seats or max(1, await limits.seats_taken(ctx.conn, ctx.who.org_id))
    page = await checkout.checkout(ctx.conn, ctx.who, stripe, ctx.settings, args.plan, seats, args.addons)
    extra = f" and {', '.join(args.addons)}" if args.addons else ""
    return Done(f"Open Stripe Checkout to subscribe to {args.plan}{extra} with {seats} seats: {page.url}", dump(page))


async def portal(ctx: Context, _: NoArgs) -> Done:
    page = await checkout.portal(ctx.conn, ctx.who, ctx.stripe(), ctx.settings)
    return Done(f"Open Stripe's billing portal (card, invoices, cancel): {page.url}", dump(page))


async def seats(ctx: Context, args: SeatsArgs) -> Done:
    changed = await changes.change_seats(ctx.conn, ctx.who, ctx.stripe(), args.seats)
    return Done(f"Your org has {changed.seats} seats now, {changed.seats_taken} taken.", {"org": dump(changed)})


TOOLS: tuple[Tool, ...] = (
    Tool(
        "upgrade",
        "Upgrade",
        "Subscribe to a Glyphh plan, with any add-ons (answers Stripe Checkout's address to open) or, when already "
        "subscribed, change to it, prorated (add-ons then with add_mod). Only the org's admin can.",
        UpgradeArgs,
        upgrade,
    ),
    Tool(
        "billing_portal",
        "Manage billing",
        "Stripe's billing portal address: card, invoices, cancel. Only the org's admin can.",
        NoArgs,
        portal,
        True,
    ),
    Tool("seats", "Change seats", "Change the org's seats, prorated. Only the org's admin can.", SeatsArgs, seats),
)
