from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="TeamChange")


@_attrs_define
class TeamChange:
    """
    Attributes:
        limit_connections (bool | None | Unset):
        limit_models (bool | None | Unset):
        name (None | str | Unset):
    """

    limit_connections: bool | Unset | None = UNSET
    limit_models: bool | Unset | None = UNSET
    name: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        limit_connections: bool | Unset | None
        if isinstance(self.limit_connections, Unset):
            limit_connections = UNSET
        else:
            limit_connections = self.limit_connections

        limit_models: bool | Unset | None
        if isinstance(self.limit_models, Unset):
            limit_models = UNSET
        else:
            limit_models = self.limit_models

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if limit_connections is not UNSET:
            field_dict["limit_connections"] = limit_connections
        if limit_models is not UNSET:
            field_dict["limit_models"] = limit_models
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_limit_connections(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        limit_connections = _parse_limit_connections(d.pop("limit_connections", UNSET))

        def _parse_limit_models(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        limit_models = _parse_limit_models(d.pop("limit_models", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        team_change = cls(
            limit_connections=limit_connections,
            limit_models=limit_models,
            name=name,
        )

        team_change.additional_properties = d
        return team_change

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
