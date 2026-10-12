from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="NextVersion")


@_attrs_define
class NextVersion:
    """
    Attributes:
        monthly_credit_cents (int):
        price_cents (int):
        extra_machine_cents (int | None | Unset):
        included_machines (int | None | Unset):
        max_seats (int | None | Unset):
        stripe_machine_price_id (None | str | Unset):
        stripe_price_id (None | str | Unset):
    """

    monthly_credit_cents: int
    price_cents: int
    extra_machine_cents: int | Unset | None = UNSET
    included_machines: int | Unset | None = UNSET
    max_seats: int | Unset | None = UNSET
    stripe_machine_price_id: str | Unset | None = UNSET
    stripe_price_id: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        monthly_credit_cents = self.monthly_credit_cents

        price_cents = self.price_cents

        extra_machine_cents: int | Unset | None
        if isinstance(self.extra_machine_cents, Unset):
            extra_machine_cents = UNSET
        else:
            extra_machine_cents = self.extra_machine_cents

        included_machines: int | Unset | None
        if isinstance(self.included_machines, Unset):
            included_machines = UNSET
        else:
            included_machines = self.included_machines

        max_seats: int | Unset | None
        if isinstance(self.max_seats, Unset):
            max_seats = UNSET
        else:
            max_seats = self.max_seats

        stripe_machine_price_id: str | Unset | None
        if isinstance(self.stripe_machine_price_id, Unset):
            stripe_machine_price_id = UNSET
        else:
            stripe_machine_price_id = self.stripe_machine_price_id

        stripe_price_id: str | Unset | None
        if isinstance(self.stripe_price_id, Unset):
            stripe_price_id = UNSET
        else:
            stripe_price_id = self.stripe_price_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "monthly_credit_cents": monthly_credit_cents,
                "price_cents": price_cents,
            }
        )
        if extra_machine_cents is not UNSET:
            field_dict["extra_machine_cents"] = extra_machine_cents
        if included_machines is not UNSET:
            field_dict["included_machines"] = included_machines
        if max_seats is not UNSET:
            field_dict["max_seats"] = max_seats
        if stripe_machine_price_id is not UNSET:
            field_dict["stripe_machine_price_id"] = stripe_machine_price_id
        if stripe_price_id is not UNSET:
            field_dict["stripe_price_id"] = stripe_price_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        monthly_credit_cents = d.pop("monthly_credit_cents")

        price_cents = d.pop("price_cents")

        def _parse_extra_machine_cents(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        extra_machine_cents = _parse_extra_machine_cents(d.pop("extra_machine_cents", UNSET))

        def _parse_included_machines(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        included_machines = _parse_included_machines(d.pop("included_machines", UNSET))

        def _parse_max_seats(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_seats = _parse_max_seats(d.pop("max_seats", UNSET))

        def _parse_stripe_machine_price_id(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        stripe_machine_price_id = _parse_stripe_machine_price_id(d.pop("stripe_machine_price_id", UNSET))

        def _parse_stripe_price_id(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        stripe_price_id = _parse_stripe_price_id(d.pop("stripe_price_id", UNSET))

        next_version = cls(
            monthly_credit_cents=monthly_credit_cents,
            price_cents=price_cents,
            extra_machine_cents=extra_machine_cents,
            included_machines=included_machines,
            max_seats=max_seats,
            stripe_machine_price_id=stripe_machine_price_id,
            stripe_price_id=stripe_price_id,
        )

        next_version.additional_properties = d
        return next_version

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
