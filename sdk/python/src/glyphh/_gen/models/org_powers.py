from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_power import OrgPower


T = TypeVar("T", bound="OrgPowers")


@_attrs_define
class OrgPowers:
    """
    Attributes:
        powers (list[OrgPower]):
        total (int):
    """

    powers: list[OrgPower]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        powers = []
        for powers_item_data in self.powers:
            powers_item = powers_item_data.to_dict()
            powers.append(powers_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "powers": powers,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_power import OrgPower

        d = dict(src_dict)
        powers = []
        _powers = d.pop("powers")
        for powers_item_data in _powers:
            powers_item = OrgPower.from_dict(powers_item_data)

            powers.append(powers_item)

        total = d.pop("total")

        org_powers = cls(
            powers=powers,
            total=total,
        )

        org_powers.additional_properties = d
        return org_powers

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
