from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Service")


@_attrs_define
class Service:
    """
    Attributes:
        blocked (None | str):
        categories (list[str]):
        connected (int):
        description (None | str):
        logo_url (None | str):
        name (str):
        slug (str):
    """

    blocked: str | None
    categories: list[str]
    connected: int
    description: str | None
    logo_url: str | None
    name: str
    slug: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        blocked: str | None
        blocked = self.blocked

        categories = self.categories

        connected = self.connected

        description: str | None
        description = self.description

        logo_url: str | None
        logo_url = self.logo_url

        name = self.name

        slug = self.slug

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "blocked": blocked,
                "categories": categories,
                "connected": connected,
                "description": description,
                "logo_url": logo_url,
                "name": name,
                "slug": slug,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_blocked(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        blocked = _parse_blocked(d.pop("blocked"))

        categories = cast(list[str], d.pop("categories"))

        connected = d.pop("connected")

        def _parse_description(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        def _parse_logo_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        logo_url = _parse_logo_url(d.pop("logo_url"))

        name = d.pop("name")

        slug = d.pop("slug")

        service = cls(
            blocked=blocked,
            categories=categories,
            connected=connected,
            description=description,
            logo_url=logo_url,
            name=name,
            slug=slug,
        )

        service.additional_properties = d
        return service

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
