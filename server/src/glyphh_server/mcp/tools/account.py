"""Who am I, my plan with its limits, features and licence key, what the org uses of it, and what each plan costs and
includes. The key is shown masked: the platform shows it whole, to copy."""

from glyphh_server.db.seed import SALES
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, amount, dump
from glyphh_server.ops import license_keys, me, nodes, plans, usage
from glyphh_server.ops.plans import PlanView


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
    return (
        f"runtime nodes {amount(plan.limits.machines)}, precedents per node {amount(plan.limits.precedents)}; "
        f"features: {', '.join(on) or 'none'}"
    )


async def key_line(ctx: Context) -> tuple[str, str | None]:
    """The org's newest live licence key, masked, and a line saying it."""
    found = await license_keys.keys(ctx.conn, ctx.who.org_id)
    live = next((k for k in found.keys if k.key == found.license_key), None)
    if live is None:
        return "Licence key: none; rrotor runs as Community (Free) without one.", None
    shown = license_keys.masked(live.key)
    return f"Licence key: {shown} ({live.tier}, expires {live.expires_at:%Y-%m-%d}); copy it on the platform.", shown


async def plan(ctx: Context, _: NoArgs) -> Done:
    found = await me.me(ctx.conn, ctx.who)
    org, p = found.org, found.plan
    renews = f", renews {org.renews_at:%Y-%m-%d}" if org.renews_at else ""
    said, key = await key_line(ctx)
    lines = [
        f"{p.name} (version {p.version}), {price(p)}: billing {org.billing_status}{renews}.",
        f"It includes {includes(p)}. Members, installs and models are unlimited.",
        said,
    ]
    return Done("\n".join(lines), {"plan": dump(p), "org": dump(org), "license_key": key})


def dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


async def show_usage(ctx: Context, _: NoArgs) -> Done:
    found = await usage.usage(ctx.conn, ctx.who.org_id)
    held, hosting = found.precedents, found.hosting
    seen = await nodes.nodes(ctx.conn, ctx.who.org_id)
    over = " (over the plan: shown, never stopped)" if seen.over else ""
    said, key = await key_line(ctx)
    lines = [
        f"Runtime nodes: {seen.count} of {amount(seen.max_nodes)}{over}.",
        f"Precedents: {held.used:,} on your fullest runtime, of {amount(held.limit)} per node.",
        said,
        f"Hosting {hosting.month} so far: {dollars(hosting.month_to_date_cents)}.",
        *(f"{m.name} ({m.size}): {dollars(m.cents)}" for m in hosting.machines),
    ]
    return Done("\n".join(lines), dump(found) | {"nodes": dump(seen), "license_key": key})


async def list_plans(ctx: Context, _: NoArgs) -> Done:
    found = await plans.list_plans(ctx.conn)
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
        "against the plan's per node, its licence key (masked), and hosting this month so far, machine by machine.",
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
