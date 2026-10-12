"""Glyphh admin, as calls, for Glyphh's staff: every org, one org and its tabs, gifts, comps, moves, disabling and
enabling; plan versions and the billing settings. `admin.catalog` and `admin.market` hold the rest
(_admin_market_specs.py). Answers are the server's JSON as plain dicts."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._admin_market_specs import CATALOG_SPECS, MARKET_SPECS
from glyphh._calls import plain_call as _call
from glyphh._gen.api.glyphh_admin import (
    admin_billing_settings,
    admin_comp_plan,
    admin_disable_org,
    admin_enable_org,
    admin_end_comp,
    admin_gift_credit,
    admin_move_orgs_to_plan,
    admin_move_plan,
    admin_next_plan_version,
    admin_org,
    admin_org_ledger,
    admin_org_machines,
    admin_org_members,
    admin_org_powers,
    admin_org_super_powers,
    admin_orgs,
    admin_plans,
    admin_set_billing_settings,
)
from glyphh._gen.models import (
    AdminNextPlanVersionFamily,
    AdminOrgsFamilyType0,
    AdminOrgsKindType0,
    AdminOrgsStateType0,
    Disable,
    Gift,
    NextVersion,
    PlanPick,
    SettingsIn,
)
from glyphh._gen.types import UNSET
from glyphh._powers import AsyncSpecApi, SpecApi

Spec = tuple[Any, dict[str, Any]]


def _o(org_id: str, **more: Any) -> dict[str, Any]:
    return {"org_id": UUID(org_id), **more}


def _orgs(
    q: str = "",
    family: str | None = None,
    state: str | None = None,
    kind: str | None = None,
    page: int = 1,
    size: int = 25,
) -> Spec:
    return _call(admin_orgs), {
        "q": q,
        "family": AdminOrgsFamilyType0(family) if family else UNSET,
        "state": AdminOrgsStateType0(state) if state else UNSET,
        "kind": AdminOrgsKindType0(kind) if kind else UNSET,
        "page": page,
        "size": size,
    }


ADMIN_SPECS: dict[str, Callable[..., Spec]] = {
    "orgs": _orgs,
    "org": lambda org_id: (_call(admin_org), _o(org_id)),
    "members": lambda org_id, q="", page=1, size=25: (_call(admin_org_members), _o(org_id, q=q, page=page, size=size)),
    "machines": lambda org_id, page=1, size=25: (_call(admin_org_machines), _o(org_id, page=page, size=size)),
    "powers": lambda org_id, kind=None, page=1, size=25: (
        _call(admin_org_powers),
        _o(org_id, kind=kind or UNSET, page=page, size=size),
    ),
    "super_powers": lambda org_id, page=1, size=25: (_call(admin_org_super_powers), _o(org_id, page=page, size=size)),
    "ledger": lambda org_id, page=1, size=25: (_call(admin_org_ledger), _o(org_id, page=page, size=size)),
    "gift": lambda org_id, cents, note: (_call(admin_gift_credit), _o(org_id, body=Gift(cents=cents, note=note))),
    "comp": lambda org_id, plan_id: (_call(admin_comp_plan), _o(org_id, body=PlanPick(plan_id=UUID(plan_id)))),
    "end_comp": lambda org_id: (_call(admin_end_comp), _o(org_id)),
    "move": lambda org_id, plan_id: (_call(admin_move_plan), _o(org_id, body=PlanPick(plan_id=UUID(plan_id)))),
    "disable": lambda org_id, reason: (_call(admin_disable_org), _o(org_id, body=Disable(reason=reason))),
    "enable": lambda org_id: (_call(admin_enable_org), _o(org_id)),
    "plans": lambda: (_call(admin_plans), {}),
    "next_version": lambda family, **version: (
        _call(admin_next_plan_version),
        {"family": AdminNextPlanVersionFamily(family), "body": NextVersion.from_dict(version)},
    ),
    "move_orgs": lambda plan_id: (_call(admin_move_orgs_to_plan), {"plan_id": UUID(plan_id)}),
    "billing_settings": lambda: (_call(admin_billing_settings), {}),
    "set_billing_settings": lambda **settings: (
        _call(admin_set_billing_settings),
        {"body": SettingsIn.from_dict(settings)},
    ),
}


class Admin(SpecApi):
    """`Glyphh(...).admin`: orgs, org, members, machines, powers, super_powers, ledger, gift, comp, end_comp, move,
    disable, enable, plans, next_version, move_orgs, billing_settings, set_billing_settings; and `.catalog` and
    `.market`."""

    def __init__(self, run: Callable[..., Any]) -> None:
        super().__init__(run, ADMIN_SPECS)
        self.catalog = SpecApi(run, CATALOG_SPECS)
        self.market = SpecApi(run, MARKET_SPECS)


class AsyncAdmin(AsyncSpecApi):
    """The same calls, awaited."""

    def __init__(self, run: Callable[..., Any]) -> None:
        super().__init__(run, ADMIN_SPECS)
        self.catalog = AsyncSpecApi(run, CATALOG_SPECS)
        self.market = AsyncSpecApi(run, MARKET_SPECS)
