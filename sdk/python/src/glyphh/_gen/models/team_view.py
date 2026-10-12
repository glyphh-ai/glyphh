from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="TeamView")


@_attrs_define
class TeamView:
    """
    Attributes:
        allowed_connections (int):
        allowed_models (int):
        id (UUID):
        limit_connections (bool):
        limit_models (bool):
        members (int):
        name (str):
    """

    allowed_connections: int
    allowed_models: int
    id: UUID
    limit_connections: bool
    limit_models: bool
    members: int
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        allowed_connections = self.allowed_connections

        allowed_models = self.allowed_models

        id = str(self.id)

        limit_connections = self.limit_connections

        limit_models = self.limit_models

        members = self.members

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "allowed_connections": allowed_connections,
                "allowed_models": allowed_models,
                "id": id,
                "limit_connections": limit_connections,
                "limit_models": limit_models,
                "members": members,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        allowed_connections = d.pop("allowed_connections")

        allowed_models = d.pop("allowed_models")

        id = UUID(d.pop("id"))

        limit_connections = d.pop("limit_connections")

        limit_models = d.pop("limit_models")

        members = d.pop("members")

        name = d.pop("name")

        team_view = cls(
            allowed_connections=allowed_connections,
            allowed_models=allowed_models,
            id=id,
            limit_connections=limit_connections,
            limit_models=limit_models,
            members=members,
            name=name,
        )

        team_view.additional_properties = d
        return team_view

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
