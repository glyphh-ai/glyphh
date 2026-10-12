from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.face import Face
    from ..models.installed_page_counts import InstalledPageCounts


T = TypeVar("T", bound="InstalledPage")


@_attrs_define
class InstalledPage:
    """
    Attributes:
        counts (InstalledPageCounts):
        machine (str):
        super_powers (list[Face]):
        total (int):
    """

    counts: InstalledPageCounts
    machine: str
    super_powers: list[Face]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        counts = self.counts.to_dict()

        machine = self.machine

        super_powers = []
        for super_powers_item_data in self.super_powers:
            super_powers_item = super_powers_item_data.to_dict()
            super_powers.append(super_powers_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "counts": counts,
                "machine": machine,
                "super_powers": super_powers,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.face import Face
        from ..models.installed_page_counts import InstalledPageCounts

        d = dict(src_dict)
        counts = InstalledPageCounts.from_dict(d.pop("counts"))

        machine = d.pop("machine")

        super_powers = []
        _super_powers = d.pop("super_powers")
        for super_powers_item_data in _super_powers:
            super_powers_item = Face.from_dict(super_powers_item_data)

            super_powers.append(super_powers_item)

        total = d.pop("total")

        installed_page = cls(
            counts=counts,
            machine=machine,
            super_powers=super_powers,
            total=total,
        )

        installed_page.additional_properties = d
        return installed_page

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
