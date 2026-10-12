from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_machine import OrgMachine


T = TypeVar("T", bound="OrgMachines")


@_attrs_define
class OrgMachines:
    """
    Attributes:
        machines (list[OrgMachine]):
        total (int):
    """

    machines: list[OrgMachine]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        machines = []
        for machines_item_data in self.machines:
            machines_item = machines_item_data.to_dict()
            machines.append(machines_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "machines": machines,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_machine import OrgMachine

        d = dict(src_dict)
        machines = []
        _machines = d.pop("machines")
        for machines_item_data in _machines:
            machines_item = OrgMachine.from_dict(machines_item_data)

            machines.append(machines_item)

        total = d.pop("total")

        org_machines = cls(
            machines=machines,
            total=total,
        )

        org_machines.additional_properties = d
        return org_machines

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
