from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AdminProvider")


@_attrs_define
class AdminProvider:
    """
    Attributes:
        active (bool):
        base_url (None | str):
        id (UUID):
        logo_dark_key (None | str):
        logo_key (None | str):
        models (int):
        models_on (int):
        name (str):
        no_description (int):
        powers (int):
        removed_at (datetime.datetime | None):
        slug (str):
        sort (int):
    """

    active: bool
    base_url: str | None
    id: UUID
    logo_dark_key: str | None
    logo_key: str | None
    models: int
    models_on: int
    name: str
    no_description: int
    powers: int
    removed_at: datetime.datetime | None
    slug: str
    sort: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        active = self.active

        base_url: str | None
        base_url = self.base_url

        id = str(self.id)

        logo_dark_key: str | None
        logo_dark_key = self.logo_dark_key

        logo_key: str | None
        logo_key = self.logo_key

        models = self.models

        models_on = self.models_on

        name = self.name

        no_description = self.no_description

        powers = self.powers

        removed_at: str | None
        if isinstance(self.removed_at, datetime.datetime):
            removed_at = self.removed_at.isoformat()
        else:
            removed_at = self.removed_at

        slug = self.slug

        sort = self.sort

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "active": active,
                "base_url": base_url,
                "id": id,
                "logo_dark_key": logo_dark_key,
                "logo_key": logo_key,
                "models": models,
                "models_on": models_on,
                "name": name,
                "no_description": no_description,
                "powers": powers,
                "removed_at": removed_at,
                "slug": slug,
                "sort": sort,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        active = d.pop("active")

        def _parse_base_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        base_url = _parse_base_url(d.pop("base_url"))

        id = UUID(d.pop("id"))

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

        models_on = d.pop("models_on")

        name = d.pop("name")

        no_description = d.pop("no_description")

        powers = d.pop("powers")

        def _parse_removed_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                removed_at_type_0 = datetime.datetime.fromisoformat(data)

                return removed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        removed_at = _parse_removed_at(d.pop("removed_at"))

        slug = d.pop("slug")

        sort = d.pop("sort")

        admin_provider = cls(
            active=active,
            base_url=base_url,
            id=id,
            logo_dark_key=logo_dark_key,
            logo_key=logo_key,
            models=models,
            models_on=models_on,
            name=name,
            no_description=no_description,
            powers=powers,
            removed_at=removed_at,
            slug=slug,
            sort=sort,
        )

        admin_provider.additional_properties = d
        return admin_provider

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
