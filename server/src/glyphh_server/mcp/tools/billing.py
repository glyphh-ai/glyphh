"""Subscribing or changing plan, and Stripe's portal: the admin's, through the existing billing code."""

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.billing import changes, checkout


class UpgradeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str = Field(
        min_length=1, max_length=40, description="The plan's name, as plans lists it: Basic, Pro, Team or Free"
    )


async def upgrade(ctx: Context, args: UpgradeArgs) -> Done:
    org = await checkout.billing_row(ctx.conn, ctx.who.org_id)
    stripe = ctx.stripe()
    if org.stripe_subscription_id is not None:
        changed = await changes.change_plan(ctx.conn, ctx.who, stripe, args.plan, ctx.settings.stripe_price_ada)
        return Done(f"Your org is on {changed.plan.name} now, prorated.", {"org": dump(changed)})
    page = await checkout.checkout(ctx.conn, ctx.who, stripe, ctx.settings, args.plan)
    return Done(f"Open Stripe Checkout to subscribe to {args.plan}: {page.url}", dump(page))


async def portal(ctx: Context, _: NoArgs) -> Done:
    page = await checkout.portal(ctx.conn, ctx.who, ctx.stripe(), ctx.settings)
    return Done(f"Open Stripe's billing portal (card, invoices, cancel): {page.url}", dump(page))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "upgrade",
        "Upgrade",
        "Subscribe to Basic, Pro or Team (answers Stripe Checkout's address to open) or, when already subscribed, "
        "change to another plan, prorated; Free cancels the subscription. Enterprise is by contract (sales@glyphh.ai). "
        "Only the org's admin can.",
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
)
