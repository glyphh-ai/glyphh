from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="PaymentCard")


@_attrs_define
class PaymentCard:
    """
    Attributes:
        brand (str):
        exp_month (int | None):
        exp_year (int | None):
        last4 (str):
    """

    brand: str
    exp_month: int | None
    exp_year: int | None
    last4: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        brand = self.brand

        exp_month: int | None
        exp_month = self.exp_month

        exp_year: int | None
        exp_year = self.exp_year

        last4 = self.last4

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "brand": brand,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "last4": last4,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        brand = d.pop("brand")

        def _parse_exp_month(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        exp_month = _parse_exp_month(d.pop("exp_month"))

        def _parse_exp_year(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        exp_year = _parse_exp_year(d.pop("exp_year"))

        last4 = d.pop("last4")

        payment_card = cls(
            brand=brand,
            exp_month=exp_month,
            exp_year=exp_year,
            last4=last4,
        )

        payment_card.additional_properties = d
        return payment_card

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
