from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.credit import Credit
    from ..models.plan_view import PlanView


T = TypeVar("T", bound="OrgOverview")


@_attrs_define
class OrgOverview:
    """
    Attributes:
        created_at (datetime.datetime):
        credit (Credit):
        disabled_at (datetime.datetime | None):
        disabled_reason (None | str):
        id (UUID):
        machines (int):
        machines_online (int):
        members (int):
        name (str):
        open_invites (int):
        pending_plan (None | PlanView):
        pending_plan_at (datetime.datetime | None):
        personal (bool):
        plan (PlanView):
        powers (int):
        seats (int):
        status (str):
        stripe_customer_id (None | str):
        super_powers (int):
    """

    created_at: datetime.datetime
    credit: Credit
    disabled_at: datetime.datetime | None
    disabled_reason: str | None
    id: UUID
    machines: int
    machines_online: int
    members: int
    name: str
    open_invites: int
    pending_plan: PlanView | None
    pending_plan_at: datetime.datetime | None
    personal: bool
    plan: PlanView
    powers: int
    seats: int
    status: str
    stripe_customer_id: str | None
    super_powers: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.plan_view import PlanView

        created_at = self.created_at.isoformat()

        credit = self.credit.to_dict()

        disabled_at: str | None
        if isinstance(self.disabled_at, datetime.datetime):
            disabled_at = self.disabled_at.isoformat()
        else:
            disabled_at = self.disabled_at

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        id = str(self.id)

        machines = self.machines

        machines_online = self.machines_online

        members = self.members

        name = self.name

        open_invites = self.open_invites

        pending_plan: dict[str, Any] | None
        if isinstance(self.pending_plan, PlanView):
            pending_plan = self.pending_plan.to_dict()
        else:
            pending_plan = self.pending_plan

        pending_plan_at: str | None
        if isinstance(self.pending_plan_at, datetime.datetime):
            pending_plan_at = self.pending_plan_at.isoformat()
        else:
            pending_plan_at = self.pending_plan_at

        personal = self.personal

        plan = self.plan.to_dict()

        powers = self.powers

        seats = self.seats

        status = self.status

        stripe_customer_id: str | None
        stripe_customer_id = self.stripe_customer_id

        super_powers = self.super_powers

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "credit": credit,
                "disabled_at": disabled_at,
                "disabled_reason": disabled_reason,
                "id": id,
                "machines": machines,
                "machines_online": machines_online,
                "members": members,
                "name": name,
                "open_invites": open_invites,
                "pending_plan": pending_plan,
                "pending_plan_at": pending_plan_at,
                "personal": personal,
                "plan": plan,
                "powers": powers,
                "seats": seats,
                "status": status,
                "stripe_customer_id": stripe_customer_id,
                "super_powers": super_powers,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credit import Credit
        from ..models.plan_view import PlanView

        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        credit = Credit.from_dict(d.pop("credit"))

        def _parse_disabled_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                disabled_at_type_0 = datetime.datetime.fromisoformat(data)

                return disabled_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        disabled_at = _parse_disabled_at(d.pop("disabled_at"))

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        id = UUID(d.pop("id"))

        machines = d.pop("machines")

        machines_online = d.pop("machines_online")

        members = d.pop("members")

        name = d.pop("name")

        open_invites = d.pop("open_invites")

        def _parse_pending_plan(data: object) -> PlanView | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                pending_plan_type_0 = PlanView.from_dict(data)

                return pending_plan_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | PlanView, data)

        pending_plan = _parse_pending_plan(d.pop("pending_plan"))

        def _parse_pending_plan_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                pending_plan_at_type_0 = datetime.datetime.fromisoformat(data)

                return pending_plan_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        pending_plan_at = _parse_pending_plan_at(d.pop("pending_plan_at"))

        personal = d.pop("personal")

        plan = PlanView.from_dict(d.pop("plan"))

        powers = d.pop("powers")

        seats = d.pop("seats")

        status = d.pop("status")

        def _parse_stripe_customer_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        stripe_customer_id = _parse_stripe_customer_id(d.pop("stripe_customer_id"))

        super_powers = d.pop("super_powers")

        org_overview = cls(
            created_at=created_at,
            credit=credit,
            disabled_at=disabled_at,
            disabled_reason=disabled_reason,
            id=id,
            machines=machines,
            machines_online=machines_online,
            members=members,
            name=name,
            open_invites=open_invites,
            pending_plan=pending_plan,
            pending_plan_at=pending_plan_at,
            personal=personal,
            plan=plan,
            powers=powers,
            seats=seats,
            status=status,
            stripe_customer_id=stripe_customer_id,
            super_powers=super_powers,
        )

        org_overview.additional_properties = d
        return org_overview

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
