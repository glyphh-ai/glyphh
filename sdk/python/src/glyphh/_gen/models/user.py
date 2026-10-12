from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="User")


@_attrs_define
class User:
    """A super power that uses a power, and how (a folder's read or write).

    Attributes:
        access (None | str):
        id (UUID):
        name (str):
    """

    access: str | None
    id: UUID
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access: str | None
        access = self.access

        id = str(self.id)

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "access": access,
                "id": id,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_access(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        access = _parse_access(d.pop("access"))

        id = UUID(d.pop("id"))

        name = d.pop("name")

        user = cls(
            access=access,
            id=id,
            name=name,
        )

        user.additional_properties = d
        return user

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
