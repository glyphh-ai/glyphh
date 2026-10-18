"""Who am I, my plan with its limits and features, and what each plan costs and includes."""

from glyphh_server.db.seed import SALES
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, amount, dump
from glyphh_server.ops import me, plans
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
        f"hosted machines {amount(plan.limits.machines)}, managed precedents {amount(plan.limits.precedents)}; "
        f"features: {', '.join(on) or 'none'}"
    )


async def plan(ctx: Context, _: NoArgs) -> Done:
    found = await me.me(ctx.conn, ctx.who)
    org, p = found.org, found.plan
    renews = f", renews {org.renews_at:%Y-%m-%d}" if org.renews_at else ""
    lines = [
        f"{p.name} (version {p.version}), {price(p)}: billing {org.billing_status}{renews}.",
        f"It includes {includes(p)}. Members, installs and local or self-hosted precedents are unlimited.",
    ]
    return Done("\n".join(lines), {"plan": dump(p), "org": dump(org)})


async def list_plans(ctx: Context, _: NoArgs) -> Done:
    found = await plans.list_plans(ctx.conn)
    lines = [f"{p.name}: {price(p)}; {includes(p)}" for p in found]
    return Done("\n".join(lines), {"plans": [dump(p) for p in found]})


TOOLS: tuple[Tool, ...] = (
    Tool("whoami", "Who am I", "The Glyphh account signed in: name, email, org and role.", NoArgs, whoami, True, True),
    Tool(
        "plan",
        "My plan",
        "The org's Glyphh plan: its price, hosted machines, managed precedents and features, its billing status and "
        "when it renews.",
        NoArgs,
        plan,
        True,
        True,
    ),
    Tool(
        "plans",
        "Glyphh plans",
        "What each Glyphh plan costs and includes: hosted machines, managed precedents and features. Never per seat, "
        "per model or per install.",
        NoArgs,
        list_plans,
        True,
    ),
)
