from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CrewFace")


@_attrs_define
class CrewFace:
    """A super power as a thread shows it: its face and its name.

    Attributes:
        avatar_color (None | str):
        avatar_variant (int):
        id (UUID):
        name (str):
    """

    avatar_color: str | None
    avatar_variant: int
    id: UUID
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        avatar_color: str | None
        avatar_color = self.avatar_color

        avatar_variant = self.avatar_variant

        id = str(self.id)

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "avatar_color": avatar_color,
                "avatar_variant": avatar_variant,
                "id": id,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_avatar_color(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        avatar_color = _parse_avatar_color(d.pop("avatar_color"))

        avatar_variant = d.pop("avatar_variant")

        id = UUID(d.pop("id"))

        name = d.pop("name")

        crew_face = cls(
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            id=id,
            name=name,
        )

        crew_face.additional_properties = d
        return crew_face

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
