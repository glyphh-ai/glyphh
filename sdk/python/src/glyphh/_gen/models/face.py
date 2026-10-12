from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Face")


@_attrs_define
class Face:
    """A super power as a machine shows it: its face, its name, what it is doing there.

    Attributes:
        avatar_color (None | str):
        avatar_variant (int):
        description (str):
        id (UUID):
        last_active_at (datetime.datetime | None):
        name (str):
        status (str):
    """

    avatar_color: None | str
    avatar_variant: int
    description: str
    id: UUID
    last_active_at: datetime.datetime | None
    name: str
    status: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        avatar_color: None | str
        avatar_color = self.avatar_color

        avatar_variant = self.avatar_variant

        description = self.description

        id = str(self.id)

        last_active_at: None | str
        if isinstance(self.last_active_at, datetime.datetime):
            last_active_at = self.last_active_at.isoformat()
        else:
            last_active_at = self.last_active_at

        name = self.name

        status = self.status

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "avatar_color": avatar_color,
                "avatar_variant": avatar_variant,
                "description": description,
                "id": id,
                "last_active_at": last_active_at,
                "name": name,
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_avatar_color(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        avatar_color = _parse_avatar_color(d.pop("avatar_color"))

        avatar_variant = d.pop("avatar_variant")

        description = d.pop("description")

        id = UUID(d.pop("id"))

        def _parse_last_active_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_active_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_active_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_active_at = _parse_last_active_at(d.pop("last_active_at"))

        name = d.pop("name")

        status = d.pop("status")

        face = cls(
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            description=description,
            id=id,
            last_active_at=last_active_at,
            name=name,
            status=status,
        )

        face.additional_properties = d
        return face

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
