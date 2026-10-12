from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AutoTopUpChange")


@_attrs_define
class AutoTopUpChange:
    """
    Attributes:
        below_cents (int):
        on (bool):
        to_cents (int):
        monthly_cap_cents (int | None | Unset):
    """

    below_cents: int
    on: bool
    to_cents: int
    monthly_cap_cents: int | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        below_cents = self.below_cents

        on = self.on

        to_cents = self.to_cents

        monthly_cap_cents: int | Unset | None
        if isinstance(self.monthly_cap_cents, Unset):
            monthly_cap_cents = UNSET
        else:
            monthly_cap_cents = self.monthly_cap_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "below_cents": below_cents,
                "on": on,
                "to_cents": to_cents,
            }
        )
        if monthly_cap_cents is not UNSET:
            field_dict["monthly_cap_cents"] = monthly_cap_cents

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        below_cents = d.pop("below_cents")

        on = d.pop("on")

        to_cents = d.pop("to_cents")

        def _parse_monthly_cap_cents(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        monthly_cap_cents = _parse_monthly_cap_cents(d.pop("monthly_cap_cents", UNSET))

        auto_top_up_change = cls(
            below_cents=below_cents,
            on=on,
            to_cents=to_cents,
            monthly_cap_cents=monthly_cap_cents,
        )

        auto_top_up_change.additional_properties = d
        return auto_top_up_change

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
