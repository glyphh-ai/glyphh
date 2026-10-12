from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.allowed_kind import AllowedKind


T = TypeVar("T", bound="CanAdd")


@_attrs_define
class CanAdd:
    """
    Attributes:
        connections (AllowedKind):
        models (AllowedKind):
        teams (list[str]):
    """

    connections: AllowedKind
    models: AllowedKind
    teams: list[str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        connections = self.connections.to_dict()

        models = self.models.to_dict()

        teams = self.teams

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "connections": connections,
                "models": models,
                "teams": teams,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.allowed_kind import AllowedKind

        d = dict(src_dict)
        connections = AllowedKind.from_dict(d.pop("connections"))

        models = AllowedKind.from_dict(d.pop("models"))

        teams = cast(list[str], d.pop("teams"))

        can_add = cls(
            connections=connections,
            models=models,
            teams=teams,
        )

        can_add.additional_properties = d
        return can_add

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
