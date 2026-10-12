from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.user import User


T = TypeVar("T", bound="CustomRow")


@_attrs_define
class CustomRow:
    """
    Attributes:
        description (str):
        id (UUID):
        installed (bool):
        kind (str):
        name (str):
        updated_at (datetime.datetime):
        used_by (list[User]):
    """

    description: str
    id: UUID
    installed: bool
    kind: str
    name: str
    updated_at: datetime.datetime
    used_by: list[User]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        id = str(self.id)

        installed = self.installed

        kind = self.kind

        name = self.name

        updated_at = self.updated_at.isoformat()

        used_by = []
        for used_by_item_data in self.used_by:
            used_by_item = used_by_item_data.to_dict()
            used_by.append(used_by_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "description": description,
                "id": id,
                "installed": installed,
                "kind": kind,
                "name": name,
                "updated_at": updated_at,
                "used_by": used_by,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user import User

        d = dict(src_dict)
        description = d.pop("description")

        id = UUID(d.pop("id"))

        installed = d.pop("installed")

        kind = d.pop("kind")

        name = d.pop("name")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        used_by = []
        _used_by = d.pop("used_by")
        for used_by_item_data in _used_by:
            used_by_item = User.from_dict(used_by_item_data)

            used_by.append(used_by_item)

        custom_row = cls(
            description=description,
            id=id,
            installed=installed,
            kind=kind,
            name=name,
            updated_at=updated_at,
            used_by=used_by,
        )

        custom_row.additional_properties = d
        return custom_row

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
