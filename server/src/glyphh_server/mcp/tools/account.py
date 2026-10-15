"""Who am I, my plan with each mod's limits and what is used, and what each plan includes."""

from typing import Any

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


def mod_lines(plan: PlanView, used: dict[str, dict[str, int]]) -> list[str]:
    lines = []
    for slug, mod in plan.mods.items():
        parts = []
        for limit, allowed in mod.limits.items():
            seen = used.get(slug, {}).get(limit)
            parts.append(f"{limit} {amount(allowed)}" if seen is None else f"{limit} {seen} of {amount(allowed)}")
        lines.append(f"{slug}: {', '.join(parts)}")
    return lines


def price(plan: PlanView) -> str:
    return f"${plan.seat_price_cents / 100:g} per seat a month"


async def plan(ctx: Context, _: NoArgs) -> Done:
    found = await me.me(ctx.conn, ctx.who)
    org, used, p = found.org, found.used, found.plan
    renews = f", renews {org.renews_at:%Y-%m-%d}" if org.renews_at else ""
    lines = [
        f"{p.name} (version {p.version}), {price(p)}: {org.seats} seats, billing {org.billing_status}{renews}.",
        f"Members {used.members} of {amount(p.limits.members)}; "
        f"installs {used.installs} of {amount(p.limits.installs)}.",
        *mod_lines(p, used.mods),
    ]
    data: dict[str, Any] = {"plan": dump(p), "used": dump(used), "org": dump(org)}
    return Done("\n".join(lines), data)


async def list_plans(ctx: Context, _: NoArgs) -> Done:
    found = await plans.list_plans(ctx.conn)
    lines = [
        f"{p.name}: {price(p)}; members {amount(p.limits.members)}, installs {amount(p.limits.installs)}; "
        + "; ".join(mod_lines(p, {}))
        for p in found
    ]
    return Done("\n".join(lines), {"plans": [dump(p) for p in found]})


TOOLS: tuple[Tool, ...] = (
    Tool("whoami", "Who am I", "The Glyphh account signed in: name, email, org and role.", NoArgs, whoami, True, True),
    Tool(
        "plan",
        "My plan",
        "The org's Glyphh plan: each mod it includes with that mod's limits and what is used, the seats, billing "
        "status and when it renews.",
        NoArgs,
        plan,
        True,
        True,
    ),
    Tool(
        "plans",
        "Glyphh plans",
        "What each Glyphh plan costs per seat and includes: account limits, each mod and its limits.",
        NoArgs,
        list_plans,
        True,
    ),
)
