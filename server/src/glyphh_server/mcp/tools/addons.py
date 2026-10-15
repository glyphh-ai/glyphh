"""The add-ons: the catalog for the org's plan and what the org has; adding or removing one. Adding and removing ask
twice: the first call answers the prorated price and changes nothing, the same call with confirm applies it."""

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, amount, dump
from glyphh_server.ops import addons
from glyphh_server.ops.addons import AddonView
from glyphh_server.ops.billing import addons as billing
from glyphh_server.ops.billing.addons import Action


class ModArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mod: str = Field(min_length=1, max_length=40, description="The add-on's mod, as addons lists it")
    confirm: bool = Field(default=False, description="false: show the prorated price only; true: apply it")
    proration_date: int | None = Field(
        default=None, description="The first call's proration_date, so the charge is exactly what it showed"
    )


def money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}${abs(cents) / 100:.2f}"


def line(a: AddonView) -> str:
    unit = "per seat " if a.per_seat else ""
    state = "added" if a.added else "available" if a.allowed else "not sold with your plan"
    limits = ", ".join(f"{k} {amount(v)}" for k, v in (a.limits or {}).items())
    return f"{a.mod}: {money(a.price_cents)} {unit}a month ({money(a.monthly_cents)} for you), {state}" + (
        f"; {limits}" if limits else ""
    )


async def list_addons(ctx: Context, _: NoArgs) -> Done:
    found = await addons.list_addons(ctx.conn, ctx.who.org_id)
    return Done("\n".join(line(a) for a in found) or "No add-ons.", {"addons": [dump(a) for a in found]})


async def _change(ctx: Context, args: ModArgs, action: Action) -> Done:
    stripe = ctx.stripe()
    if not args.confirm:
        seen = await billing.preview(ctx.conn, ctx.who, stripe, args.mod, action)
        verb = "Adding" if action == "add" else "Removing"
        tool = "add_mod" if action == "add" else "remove_mod"
        text = (
            f"{verb} {seen.mod} changes your next invoice by {money(seen.prorated_cents)} now, prorated; "
            f"it is {money(seen.monthly_cents)} a month. Nothing has changed yet: call {tool} again with "
            f'mod "{seen.mod}", confirm true and proration_date {seen.proration_date} to do it.'
        )
        return Done(text, {"preview": dump(seen), "confirm_needed": True})
    found = await billing.change(ctx.conn, ctx.who, stripe, args.mod, action, args.proration_date)
    done = "added" if action == "add" else "removed"
    return Done(f"{args.mod.strip().lower()} is {done}, prorated.", {"addons": [dump(a) for a in found]})


async def add_mod(ctx: Context, args: ModArgs) -> Done:
    return await _change(ctx, args, "add")


async def remove_mod(ctx: Context, args: ModArgs) -> Done:
    return await _change(ctx, args, "remove")


TOOLS: tuple[Tool, ...] = (
    Tool(
        "addons",
        "Add-ons",
        "The Glyphh add-ons for the org's plan (every mod but Workspaces): each one's price, its limits on the plan, "
        "and which the org has.",
        NoArgs,
        list_addons,
        True,
    ),
    Tool(
        "add_mod",
        "Add a mod",
        "Add a mod to the org's subscription, prorated. The first call only shows what it costs; call again with "
        "confirm true (and the proration_date it gave) to add it. Only the org's admin can.",
        ModArgs,
        add_mod,
    ),
    Tool(
        "remove_mod",
        "Remove a mod",
        "Remove a mod from the org's subscription, prorated (a credit). The first call only shows the credit; call "
        "again with confirm true (and the proration_date it gave) to remove it. Only the org's admin can.",
        ModArgs,
        remove_mod,
    ),
)
