"""The Glyphh-hosted models' tokens and overage balance in the connector's words (docs/specs/tokens.md), for the plan
and usage tools, and topping the balance up: the admin's, through the same code as POST /v1/billing/topup. Offered
only while hosted models are on."""

from typing import Any

from glyphh_server.llm import registry, usage
from glyphh_server.llm.usage import Balance, Tokens
from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops.billing import topup
from glyphh_server.ops.billing.topup import TopupIn
from glyphh_server.ops.plans import PlanView


def dollars(cents: float) -> str:
    return f"-${-cents / 100:,.2f}" if cents < 0 else f"${cents / 100:,.2f}"


def lines(tokens: Tokens | None, balance: Balance | None) -> list[str]:
    """The month's tokens and the balance in words; nothing while hosted models are off."""
    if tokens is None or balance is None:
        return []
    most = "by contract" if tokens.max is None else f"{tokens.max:,}"
    past = f", {tokens.over_used:,} past it, charged to the balance" if tokens.over_used else ""
    low = " (low: add funds with topup)" if balance.low else ""
    again = f"the count starts again {tokens.resets_at}"
    return [
        f"Hosted-model tokens {tokens.month}: {tokens.used:,} of {most}{past}; {again}.",
        f"Overage balance: {dollars(balance.cents)}{low}.",
    ]


def allowance(plan: PlanView) -> str:
    """A plan's tokens a month, for the plans tool."""
    most = "by contract" if plan.llm_tokens is None else f"{plan.llm_tokens:,}"
    return f"; hosted-model tokens a month {most}, then charged to a prepaid balance"


def rates(hosted: bool) -> tuple[list[str], dict[str, Any]]:
    """The hosted models and their rates, while they are on: the plans tool's lines and data."""
    if not hosted:
        return [], {}
    found = registry.listing().models
    said = [
        f"{m.name} ({m.id}): {dollars(m.input_cents_per_mtok)} per million input tokens, "
        f"{dollars(m.output_cents_per_mtok)} per million output tokens past the allowance."
        for m in found
    ]
    return said, {"models": [dump(m) for m in found]}


async def of_plan(ctx: Context, most: int | None) -> tuple[list[str], dict[str, Any]]:
    """The plan tool's tokens and balance, while hosted models are on."""
    if not ctx.settings.hosted:
        return [], {}
    tokens = await usage.tokens(ctx.conn, ctx.who.org_id, most)
    balance = await usage.balance(ctx.conn, ctx.who.org_id)
    return lines(tokens, balance), {"tokens": dump(tokens), "balance": dump(balance)}


async def add_funds(ctx: Context, args: TopupIn) -> Done:
    page = await topup.topup(ctx.conn, ctx.who, ctx.stripe(), ctx.settings, args.amount_cents)
    said = f"Open Stripe Checkout to add {dollars(args.amount_cents)} to your overage balance: {page.url}"
    return Done(said, dump(page))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "topup",
        "Add funds",
        "Stripe Checkout's address to add $10 to $1,000 (in cents: amount_cents 1000 to 100000) to the overage balance "
        "Glyphh-hosted models draw on past the plan's monthly tokens; credited once paid. Only the org's admin can.",
        TopupIn,
        add_funds,
    ),
)
