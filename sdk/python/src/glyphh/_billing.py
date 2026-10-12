"""My org's billing: the plans, its credit, and (org admins) the Billing page. Paying happens in Stripe's
Payment Element on the page: these calls start it (a client secret) and read what Stripe confirmed.
Answers are the server's JSON as plain dicts, amounts in US cents."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from glyphh._calls import Call
from glyphh._gen.api.billing import (
    add_funds,
    change_plan,
    check_auto_top_up,
    get_billing,
    list_invoices,
    list_ledger,
    list_plans,
    list_top_ups,
    next_invoice,
    open_billing_portal,
    org_credit,
    preview_plan_change,
    set_auto_top_up,
    spend_by_day,
    start_card_setup,
    sync_billing,
)
from glyphh._gen.models.auto_top_up_change import AutoTopUpChange
from glyphh._gen.models.funds_in import FundsIn
from glyphh._gen.models.plan_in import PlanIn
from glyphh._gen.types import UNSET


def _plain(parsed: Any) -> Any:
    if isinstance(parsed, list):
        return [_plain(p) for p in parsed]
    return parsed.to_dict() if hasattr(parsed, "to_dict") else parsed


def _call(operation: Any) -> Call:
    return Call(operation, lambda r: 200 <= int(r.status_code) < 300, _plain)


PLANS, CREDIT, GET, SYNC = _call(list_plans), _call(org_credit), _call(get_billing), _call(sync_billing)
ADD_FUNDS, TOP_UPS, SET_AUTO, CHECK_AUTO = (
    _call(add_funds),
    _call(list_top_ups),
    _call(set_auto_top_up),
    _call(check_auto_top_up),
)
CARD, PREVIEW, CHANGE = _call(start_card_setup), _call(preview_plan_change), _call(change_plan)
LEDGER, SPEND, INVOICES, NEXT, PORTAL = (
    _call(list_ledger),
    _call(spend_by_day),
    _call(list_invoices),
    _call(next_invoice),
    _call(open_billing_portal),
)


def _auto(on: bool, below_cents: int, to_cents: int, monthly_cap_cents: int | None) -> dict[str, Any]:
    return {
        "body": AutoTopUpChange(on=on, below_cents=below_cents, to_cents=to_cents, monthly_cap_cents=monthly_cap_cents)
    }


def _plan(plan_id: str) -> dict[str, Any]:
    return {"body": PlanIn(plan_id=UUID(plan_id))}


def _invoices(after: str | None, limit: int) -> dict[str, Any]:
    return {"after": after if after else UNSET, "limit": limit}


class Billing:
    """`Glyphh(...).billing`: the same calls for ordinary code."""

    def __init__(self, run: Callable[..., Any]) -> None:
        self._run = run

    def plans(self) -> Any:
        """The plans on sale now, each its current version."""
        return self._run(PLANS)

    def credit(self) -> Any:
        """My org's plan, when it renews, and its credit this period (any member)."""
        return self._run(CREDIT)

    def get(self) -> Any:
        """The Billing page in one read (org admins)."""
        return self._run(GET)

    def add_funds(self, amount_cents: int) -> Any:
        """Start adding credit ($5 to $10,000); confirm its client secret in Stripe's Payment Element."""
        return self._run(ADD_FUNDS, body=FundsIn(amount_cents=amount_cents))

    def top_ups(self, page: int = 1, size: int = 25) -> Any:
        return self._run(TOP_UPS, page=page, size=size)

    def set_auto_top_up(
        self, *, on: bool, below_cents: int, to_cents: int, monthly_cap_cents: int | None = None
    ) -> Any:
        return self._run(SET_AUTO, **_auto(on, below_cents, to_cents, monthly_cap_cents))

    def check_auto_top_up(self) -> Any:
        return self._run(CHECK_AUTO)

    def set_up_card(self) -> Any:
        return self._run(CARD)

    def preview_plan(self, plan_id: str) -> Any:
        return self._run(PREVIEW, **_plan(plan_id))

    def change_plan(self, plan_id: str) -> Any:
        return self._run(CHANGE, **_plan(plan_id))

    def sync(self) -> Any:
        return self._run(SYNC)

    def ledger(self, page: int = 1, size: int = 50) -> Any:
        return self._run(LEDGER, page=page, size=size)

    def spend_by_day(self) -> Any:
        return self._run(SPEND)

    def invoices(self, after: str | None = None, limit: int = 25) -> Any:
        return self._run(INVOICES, **_invoices(after, limit))

    def next_invoice(self) -> Any:
        return self._run(NEXT)

    def portal(self) -> Any:
        return self._run(PORTAL)


class AsyncBilling:
    """`AsyncGlyphh(...).billing`: the same calls for asyncio code."""

    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        self._run = run

    async def plans(self) -> Any:
        return await self._run(PLANS)

    async def credit(self) -> Any:
        return await self._run(CREDIT)

    async def get(self) -> Any:
        return await self._run(GET)

    async def add_funds(self, amount_cents: int) -> Any:
        return await self._run(ADD_FUNDS, body=FundsIn(amount_cents=amount_cents))

    async def top_ups(self, page: int = 1, size: int = 25) -> Any:
        return await self._run(TOP_UPS, page=page, size=size)

    async def set_auto_top_up(
        self, *, on: bool, below_cents: int, to_cents: int, monthly_cap_cents: int | None = None
    ) -> Any:
        return await self._run(SET_AUTO, **_auto(on, below_cents, to_cents, monthly_cap_cents))

    async def check_auto_top_up(self) -> Any:
        return await self._run(CHECK_AUTO)

    async def set_up_card(self) -> Any:
        return await self._run(CARD)

    async def preview_plan(self, plan_id: str) -> Any:
        return await self._run(PREVIEW, **_plan(plan_id))

    async def change_plan(self, plan_id: str) -> Any:
        return await self._run(CHANGE, **_plan(plan_id))

    async def sync(self) -> Any:
        return await self._run(SYNC)

    async def ledger(self, page: int = 1, size: int = 50) -> Any:
        return await self._run(LEDGER, page=page, size=size)

    async def spend_by_day(self) -> Any:
        return await self._run(SPEND)

    async def invoices(self, after: str | None = None, limit: int = 25) -> Any:
        return await self._run(INVOICES, **_invoices(after, limit))

    async def next_invoice(self) -> Any:
        return await self._run(NEXT)

    async def portal(self) -> Any:
        return await self._run(PORTAL)
