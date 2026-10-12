from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgPower")


@_attrs_define
class OrgPower:
    """
    Attributes:
        created_at (datetime.datetime):
        disabled_reason (None | str):
        id (UUID):
        kind (str):
        name (str):
        owner (str):
    """

    created_at: datetime.datetime
    disabled_reason: str | None
    id: UUID
    kind: str
    name: str
    owner: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        id = str(self.id)

        kind = self.kind

        name = self.name

        owner = self.owner

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "disabled_reason": disabled_reason,
                "id": id,
                "kind": kind,
                "name": name,
                "owner": owner,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        name = d.pop("name")

        owner = d.pop("owner")

        org_power = cls(
            created_at=created_at,
            disabled_reason=disabled_reason,
            id=id,
            kind=kind,
            name=name,
            owner=owner,
        )

        org_power.additional_properties = d
        return org_power

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
