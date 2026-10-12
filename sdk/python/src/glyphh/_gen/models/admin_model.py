from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AdminModel")


@_attrs_define
class AdminModel:
    """
    Attributes:
        active (bool):
        description (None | str):
        id (UUID):
        model (str):
        name (str):
        powers (int):
        provider (str):
        provider_name (str):
        removed_at (datetime.datetime | None):
        type_ (str):
    """

    active: bool
    description: str | None
    id: UUID
    model: str
    name: str
    powers: int
    provider: str
    provider_name: str
    removed_at: datetime.datetime | None
    type_: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        active = self.active

        description: str | None
        description = self.description

        id = str(self.id)

        model = self.model

        name = self.name

        powers = self.powers

        provider = self.provider

        provider_name = self.provider_name

        removed_at: str | None
        if isinstance(self.removed_at, datetime.datetime):
            removed_at = self.removed_at.isoformat()
        else:
            removed_at = self.removed_at

        type_ = self.type_

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "active": active,
                "description": description,
                "id": id,
                "model": model,
                "name": name,
                "powers": powers,
                "provider": provider,
                "provider_name": provider_name,
                "removed_at": removed_at,
                "type": type_,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        active = d.pop("active")

        def _parse_description(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        id = UUID(d.pop("id"))

        model = d.pop("model")

        name = d.pop("name")

        powers = d.pop("powers")

        provider = d.pop("provider")

        provider_name = d.pop("provider_name")

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

        type_ = d.pop("type")

        admin_model = cls(
            active=active,
            description=description,
            id=id,
            model=model,
            name=name,
            powers=powers,
            provider=provider,
            provider_name=provider_name,
            removed_at=removed_at,
            type_=type_,
        )

        admin_model.additional_properties = d
        return admin_model

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
