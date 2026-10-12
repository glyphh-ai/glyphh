from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="MyCopy")


@_attrs_define
class MyCopy:
    """
    Attributes:
        newer (None | str):
        power_id (UUID):
        version (str):
    """

    newer: str | None
    power_id: UUID
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        newer: str | None
        newer = self.newer

        power_id = str(self.power_id)

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "newer": newer,
                "power_id": power_id,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_newer(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        newer = _parse_newer(d.pop("newer"))

        power_id = UUID(d.pop("power_id"))

        version = d.pop("version")

        my_copy = cls(
            newer=newer,
            power_id=power_id,
            version=version,
        )

        my_copy.additional_properties = d
        return my_copy

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
