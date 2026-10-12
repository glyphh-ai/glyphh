from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="GrantView")


@_attrs_define
class GrantView:
    """
    Attributes:
        access (None | str):
        denied (bool):
        disabled_reason (None | str):
        id (UUID):
        kind (str):
        name (str):
        target_id (UUID):
    """

    access: str | None
    denied: bool
    disabled_reason: str | None
    id: UUID
    kind: str
    name: str
    target_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access: str | None
        access = self.access

        denied = self.denied

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        id = str(self.id)

        kind = self.kind

        name = self.name

        target_id = str(self.target_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "access": access,
                "denied": denied,
                "disabled_reason": disabled_reason,
                "id": id,
                "kind": kind,
                "name": name,
                "target_id": target_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_access(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        access = _parse_access(d.pop("access"))

        denied = d.pop("denied")

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        name = d.pop("name")

        target_id = UUID(d.pop("target_id"))

        grant_view = cls(
            access=access,
            denied=denied,
            disabled_reason=disabled_reason,
            id=id,
            kind=kind,
            name=name,
            target_id=target_id,
        )

        grant_view.additional_properties = d
        return grant_view

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
