from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CatalogEntry")


@_attrs_define
class CatalogEntry:
    """
    Attributes:
        blocked (None | str):
        description (None | str):
        id (UUID):
        logo_key (None | str):
        model (str):
        name (str):
        provider (str):
        provider_name (str):
        type_ (str):
    """

    blocked: str | None
    description: str | None
    id: UUID
    logo_key: str | None
    model: str
    name: str
    provider: str
    provider_name: str
    type_: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        blocked: str | None
        blocked = self.blocked

        description: str | None
        description = self.description

        id = str(self.id)

        logo_key: str | None
        logo_key = self.logo_key

        model = self.model

        name = self.name

        provider = self.provider

        provider_name = self.provider_name

        type_ = self.type_

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "blocked": blocked,
                "description": description,
                "id": id,
                "logo_key": logo_key,
                "model": model,
                "name": name,
                "provider": provider,
                "provider_name": provider_name,
                "type": type_,
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

        def _parse_description(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        id = UUID(d.pop("id"))

        def _parse_logo_key(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        logo_key = _parse_logo_key(d.pop("logo_key"))

        model = d.pop("model")

        name = d.pop("name")

        provider = d.pop("provider")

        provider_name = d.pop("provider_name")

        type_ = d.pop("type")

        catalog_entry = cls(
            blocked=blocked,
            description=description,
            id=id,
            logo_key=logo_key,
            model=model,
            name=name,
            provider=provider,
            provider_name=provider_name,
            type_=type_,
        )

        catalog_entry.additional_properties = d
        return catalog_entry

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
