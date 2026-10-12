from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.auto_top_up import AutoTopUp
    from ..models.card import Card
    from ..models.credit import Credit
    from ..models.plan_view import PlanView


T = TypeVar("T", bound="Billing")


@_attrs_define
class Billing:
    """
    Attributes:
        auto_top_up (AutoTopUp):
        billing_email (None | str):
        card (Card | None):
        credit (Credit):
        extra_machines (int):
        machines_in_use (int):
        pending_plan (None | PlanView):
        pending_plan_at (datetime.datetime | None):
        plan (PlanView):
        seats_billed (int):
        seats_in_use (int):
        status (str):
        stripe_publishable_key (str):
    """

    auto_top_up: AutoTopUp
    billing_email: str | None
    card: Card | None
    credit: Credit
    extra_machines: int
    machines_in_use: int
    pending_plan: PlanView | None
    pending_plan_at: datetime.datetime | None
    plan: PlanView
    seats_billed: int
    seats_in_use: int
    status: str
    stripe_publishable_key: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.card import Card
        from ..models.plan_view import PlanView

        auto_top_up = self.auto_top_up.to_dict()

        billing_email: str | None
        billing_email = self.billing_email

        card: dict[str, Any] | None
        if isinstance(self.card, Card):
            card = self.card.to_dict()
        else:
            card = self.card

        credit = self.credit.to_dict()

        extra_machines = self.extra_machines

        machines_in_use = self.machines_in_use

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

        plan = self.plan.to_dict()

        seats_billed = self.seats_billed

        seats_in_use = self.seats_in_use

        status = self.status

        stripe_publishable_key = self.stripe_publishable_key

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "auto_top_up": auto_top_up,
                "billing_email": billing_email,
                "card": card,
                "credit": credit,
                "extra_machines": extra_machines,
                "machines_in_use": machines_in_use,
                "pending_plan": pending_plan,
                "pending_plan_at": pending_plan_at,
                "plan": plan,
                "seats_billed": seats_billed,
                "seats_in_use": seats_in_use,
                "status": status,
                "stripe_publishable_key": stripe_publishable_key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.auto_top_up import AutoTopUp
        from ..models.card import Card
        from ..models.credit import Credit
        from ..models.plan_view import PlanView

        d = dict(src_dict)
        auto_top_up = AutoTopUp.from_dict(d.pop("auto_top_up"))

        def _parse_billing_email(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        billing_email = _parse_billing_email(d.pop("billing_email"))

        def _parse_card(data: object) -> Card | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                card_type_0 = Card.from_dict(data)

                return card_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(Card | None, data)

        card = _parse_card(d.pop("card"))

        credit = Credit.from_dict(d.pop("credit"))

        extra_machines = d.pop("extra_machines")

        machines_in_use = d.pop("machines_in_use")

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

        plan = PlanView.from_dict(d.pop("plan"))

        seats_billed = d.pop("seats_billed")

        seats_in_use = d.pop("seats_in_use")

        status = d.pop("status")

        stripe_publishable_key = d.pop("stripe_publishable_key")

        billing = cls(
            auto_top_up=auto_top_up,
            billing_email=billing_email,
            card=card,
            credit=credit,
            extra_machines=extra_machines,
            machines_in_use=machines_in_use,
            pending_plan=pending_plan,
            pending_plan_at=pending_plan_at,
            plan=plan,
            seats_billed=seats_billed,
            seats_in_use=seats_in_use,
            status=status,
            stripe_publishable_key=stripe_publishable_key,
        )

        billing.additional_properties = d
        return billing

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
