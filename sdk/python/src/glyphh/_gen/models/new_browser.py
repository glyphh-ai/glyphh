from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="NewBrowser")


@_attrs_define
class NewBrowser:
    """
    Attributes:
        machine_id (UUID):
        name (str):
        super_power_id (UUID):
    """

    machine_id: UUID
    name: str
    super_power_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        machine_id = str(self.machine_id)

        name = self.name

        super_power_id = str(self.super_power_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "machine_id": machine_id,
                "name": name,
                "super_power_id": super_power_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        machine_id = UUID(d.pop("machine_id"))

        name = d.pop("name")

        super_power_id = UUID(d.pop("super_power_id"))

        new_browser = cls(
            machine_id=machine_id,
            name=name,
            super_power_id=super_power_id,
        )

        new_browser.additional_properties = d
        return new_browser

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
