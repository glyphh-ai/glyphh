from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.searched_by import SearchedBy

T = TypeVar("T", bound="Searched")


@_attrs_define
class Searched:
    """
    Attributes:
        by (SearchedBy):
        machine_id (UUID):
        name (str):
    """

    by: SearchedBy
    machine_id: UUID
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        by = self.by.value

        machine_id = str(self.machine_id)

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "by": by,
                "machine_id": machine_id,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        by = SearchedBy(d.pop("by"))

        machine_id = UUID(d.pop("machine_id"))

        name = d.pop("name")

        searched = cls(
            by=by,
            machine_id=machine_id,
            name=name,
        )

        searched.additional_properties = d
        return searched

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
