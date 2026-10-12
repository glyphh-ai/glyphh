from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="PlanView")


@_attrs_define
class PlanView:
    """
    Attributes:
        extra_machine_cents (int | None):
        family (str):
        id (UUID):
        included_machines (int | None):
        max_seats (int | None):
        monthly_credit_cents (int):
        name (str):
        on_sale (bool):
        price_cents (int):
        version (int):
    """

    extra_machine_cents: int | None
    family: str
    id: UUID
    included_machines: int | None
    max_seats: int | None
    monthly_credit_cents: int
    name: str
    on_sale: bool
    price_cents: int
    version: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        extra_machine_cents: int | None
        extra_machine_cents = self.extra_machine_cents

        family = self.family

        id = str(self.id)

        included_machines: int | None
        included_machines = self.included_machines

        max_seats: int | None
        max_seats = self.max_seats

        monthly_credit_cents = self.monthly_credit_cents

        name = self.name

        on_sale = self.on_sale

        price_cents = self.price_cents

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "extra_machine_cents": extra_machine_cents,
                "family": family,
                "id": id,
                "included_machines": included_machines,
                "max_seats": max_seats,
                "monthly_credit_cents": monthly_credit_cents,
                "name": name,
                "on_sale": on_sale,
                "price_cents": price_cents,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_extra_machine_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        extra_machine_cents = _parse_extra_machine_cents(d.pop("extra_machine_cents"))

        family = d.pop("family")

        id = UUID(d.pop("id"))

        def _parse_included_machines(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        included_machines = _parse_included_machines(d.pop("included_machines"))

        def _parse_max_seats(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        max_seats = _parse_max_seats(d.pop("max_seats"))

        monthly_credit_cents = d.pop("monthly_credit_cents")

        name = d.pop("name")

        on_sale = d.pop("on_sale")

        price_cents = d.pop("price_cents")

        version = d.pop("version")

        plan_view = cls(
            extra_machine_cents=extra_machine_cents,
            family=family,
            id=id,
            included_machines=included_machines,
            max_seats=max_seats,
            monthly_credit_cents=monthly_credit_cents,
            name=name,
            on_sale=on_sale,
            price_cents=price_cents,
            version=version,
        )

        plan_view.additional_properties = d
        return plan_view

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
