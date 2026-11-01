"""Who am I, my plan with its limits, features and licence key, what the org uses of it, and what each plan costs and
includes. The key is shown masked: the platform shows it whole, to copy."""

from typing import Any

from glyphh_ada.usage import CloudUsage
from glyphh_server.db.seed import SALES
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, amount, dump
from glyphh_server.ops import license_keys, me, nodes, plans, usage
from glyphh_server.ops.plans import CloudLimits, PlanView


async def whoami(ctx: Context, _: NoArgs) -> Done:
    found = await me.me(ctx.conn, ctx.who)
    data = {
        "id": str(found.id),
        "email": found.email,
        "name": found.name,
        "role": found.role,
        "org": {"id": str(found.org.id), "name": found.org.name},
    }
    return Done(f"{found.name or found.email} ({found.email}), {found.role} of {found.org.name}.", data)


def price(plan: PlanView) -> str:
    if plan.price_cents is None:
        return f"by contract, a {plan.interval}: talk to us at {SALES}"
    if plan.interval is None:
        return "free"
    return f"${plan.price_cents / 100:,.0f} a {plan.interval}"


def includes(plan: PlanView) -> str:
    on = [name for name, yes in plan.features.model_dump().items() if yes]
    said = (
        f"runtime nodes {amount(plan.limits.machines)}, precedents per node {amount(plan.limits.precedents)}; "
        f"features: {', '.join(on) or 'none'}"
    )
    return said if plan.cloud is None else f"{said}; {cloud_line(plan.cloud)}"


def many(value: int | None) -> str:
    return "unlimited" if value is None else f"{value:,}"


def cloud_line(c: CloudLimits) -> str:
    """Ada Cloud's limits in words: by contract where they are none."""
    if c.requests_per_month is None:
        return "Ada Cloud by contract"
    past = f"then ${(c.overage_cents_per_10k or 0) / 100:,.0f} per 10,000 more" if c.overage else "then refused"
    return (
        f"Ada Cloud {many(c.precedents)} precedents, {c.requests_per_month:,} reads a month ({past}), "
        f"{many(c.requests_per_second)} calls a second"
    )


def cloud_redis(ctx: Context) -> Any:
    """The Redis Ada Cloud's reads are counted on, while it is on (its app's)."""
    return None if ctx.ada is None else ctx.ada.redis


async def key_line(ctx: Context) -> tuple[str, str | None]:
    """The org's newest live licence key, masked, and a line saying it."""
    found = await license_keys.keys(ctx.conn, ctx.who.org_id)
    live = next((k for k in found.keys if k.key == found.license_key), None)
    if live is None:
        return "Licence key: none; rrotor runs as Community (Free) without one.", None
    shown = license_keys.masked(live.key)
    return f"Licence key: {shown} ({live.tier}, expires {live.expires_at:%Y-%m-%d}); copy it on the platform.", shown


async def plan(ctx: Context, _: NoArgs) -> Done:
    found = await me.me(ctx.conn, ctx.who, cloud_redis(ctx))
    org, p = found.org, found.plan
    renews = f", renews {org.renews_at:%Y-%m-%d}" if org.renews_at else ""
    said, key = await key_line(ctx)
    lines = [
        f"{p.name} (version {p.version}), {price(p)}: billing {org.billing_status}{renews}.",
        f"It includes {includes(p)}. Members, installs and models are unlimited.",
        said,
    ]
    return Done("\n".join(lines), {"plan": dump(p), "org": dump(org), "license_key": key})


async def show_usage(ctx: Context, _: NoArgs) -> Done:
    found = await usage.usage(ctx.conn, ctx.who.org_id, cloud_redis(ctx))
    held = found.precedents
    seen = await nodes.nodes(ctx.conn, ctx.who.org_id)
    over = " (over the plan: shown, never stopped)" if seen.over else ""
    said, key = await key_line(ctx)
    lines = [
        *cloud_used(found.cloud),
        f"Runtime nodes: {seen.count} of {amount(seen.max_nodes)}{over}.",
        f"Precedents: {held.used:,} on your fullest runtime, of {amount(held.limit)} per node.",
        said,
    ]
    return Done("\n".join(lines), dump(found) | {"nodes": dump(seen), "license_key": key})


def cloud_used(c: CloudUsage | None) -> list[str]:
    if c is None:
        return []
    reads = c.requests
    over = f", {reads.over:,} past it, metered" if reads.over else ""
    return [
        f"Ada Cloud reads {c.month}: {reads.used:,} of {many(reads.max)}{over}; the count starts again {c.resets_at}.",
        f"Ada Cloud precedents: {c.precedents.used:,} of {many(c.precedents.max)}, in {c.models} model"
        + "s" * (c.models != 1)
        + ".",
    ]


async def list_plans(ctx: Context, _: NoArgs) -> Done:
    found = await plans.list_plans(ctx.conn, ctx.ada is not None)
    lines = [f"{p.name}: {price(p)}; {includes(p)}" for p in found]
    return Done("\n".join(lines), {"plans": [dump(p) for p in found]})


TOOLS: tuple[Tool, ...] = (
    Tool("whoami", "Who am I", "The Glyphh account signed in: name, email, org and role.", NoArgs, whoami, True, True),
    Tool(
        "plan",
        "My plan",
        "The org's Glyphh plan: its price, runtime nodes, precedents per node and features, its billing status, when "
        "it renews, and its licence key (masked).",
        NoArgs,
        plan,
        True,
        True,
    ),
    Tool(
        "usage",
        "Usage",
        "What the org uses of its plan: its runtime nodes against the plan's, the precedents on its fullest runtime "
        "against the plan's per node, and its licence key (masked).",
        NoArgs,
        show_usage,
        True,
        True,
    ),
    Tool(
        "plans",
        "Glyphh plans",
        "What each Glyphh plan costs and includes: runtime nodes, precedents per node and features. Never per seat, "
        "per model or per install.",
        NoArgs,
        list_plans,
        True,
    ),
)
