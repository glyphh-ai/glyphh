from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ProviderView")


@_attrs_define
class ProviderView:
    """
    Attributes:
        blocked (None | str):
        logo_dark_key (None | str):
        logo_key (None | str):
        models (int):
        name (str):
        slug (str):
    """

    blocked: str | None
    logo_dark_key: str | None
    logo_key: str | None
    models: int
    name: str
    slug: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        blocked: str | None
        blocked = self.blocked

        logo_dark_key: str | None
        logo_dark_key = self.logo_dark_key

        logo_key: str | None
        logo_key = self.logo_key

        models = self.models

        name = self.name

        slug = self.slug

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "blocked": blocked,
                "logo_dark_key": logo_dark_key,
                "logo_key": logo_key,
                "models": models,
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

        def _parse_logo_dark_key(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        logo_dark_key = _parse_logo_dark_key(d.pop("logo_dark_key"))

        def _parse_logo_key(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        logo_key = _parse_logo_key(d.pop("logo_key"))

        models = d.pop("models")

        name = d.pop("name")

        slug = d.pop("slug")

        provider_view = cls(
            blocked=blocked,
            logo_dark_key=logo_dark_key,
            logo_key=logo_key,
            models=models,
            name=name,
            slug=slug,
        )

        provider_view.additional_properties = d
        return provider_view

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
