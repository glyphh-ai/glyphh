from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Moved")


@_attrs_define
class Moved:
    """
    Attributes:
        applies_at (datetime.datetime):
        orgs (int):
    """

    applies_at: datetime.datetime
    orgs: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        applies_at = self.applies_at.isoformat()

        orgs = self.orgs

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "applies_at": applies_at,
                "orgs": orgs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        applies_at = datetime.datetime.fromisoformat(d.pop("applies_at"))

        orgs = d.pop("orgs")

        moved = cls(
            applies_at=applies_at,
            orgs=orgs,
        )

        moved.additional_properties = d
        return moved

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
