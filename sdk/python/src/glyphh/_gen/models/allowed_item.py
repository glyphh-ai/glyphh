from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AllowedItem")


@_attrs_define
class AllowedItem:
    """
    Attributes:
        id (str):
        name (str):
        provider (None | str):
        teams (list[str]):
    """

    id: str
    name: str
    provider: str | None
    teams: list[str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        provider: str | None
        provider = self.provider

        teams = self.teams

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "provider": provider,
                "teams": teams,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        def _parse_provider(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        provider = _parse_provider(d.pop("provider"))

        teams = cast(list[str], d.pop("teams"))

        allowed_item = cls(
            id=id,
            name=name,
            provider=provider,
            teams=teams,
        )

        allowed_item.additional_properties = d
        return allowed_item

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
