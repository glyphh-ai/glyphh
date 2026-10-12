from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_super_power import OrgSuperPower


T = TypeVar("T", bound="OrgSuperPowers")


@_attrs_define
class OrgSuperPowers:
    """
    Attributes:
        super_powers (list[OrgSuperPower]):
        total (int):
    """

    super_powers: list[OrgSuperPower]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        super_powers = []
        for super_powers_item_data in self.super_powers:
            super_powers_item = super_powers_item_data.to_dict()
            super_powers.append(super_powers_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "super_powers": super_powers,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_super_power import OrgSuperPower

        d = dict(src_dict)
        super_powers = []
        _super_powers = d.pop("super_powers")
        for super_powers_item_data in _super_powers:
            super_powers_item = OrgSuperPower.from_dict(super_powers_item_data)

            super_powers.append(super_powers_item)

        total = d.pop("total")

        org_super_powers = cls(
            super_powers=super_powers,
            total=total,
        )

        org_super_powers.additional_properties = d
        return org_super_powers

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
