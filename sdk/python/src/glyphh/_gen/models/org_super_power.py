from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgSuperPower")


@_attrs_define
class OrgSuperPower:
    """
    Attributes:
        created_at (datetime.datetime):
        glyphh (bool):
        id (UUID):
        live (bool):
        name (str):
        owner (str):
    """

    created_at: datetime.datetime
    glyphh: bool
    id: UUID
    live: bool
    name: str
    owner: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        glyphh = self.glyphh

        id = str(self.id)

        live = self.live

        name = self.name

        owner = self.owner

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "glyphh": glyphh,
                "id": id,
                "live": live,
                "name": name,
                "owner": owner,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        glyphh = d.pop("glyphh")

        id = UUID(d.pop("id"))

        live = d.pop("live")

        name = d.pop("name")

        owner = d.pop("owner")

        org_super_power = cls(
            created_at=created_at,
            glyphh=glyphh,
            id=id,
            live=live,
            name=name,
            owner=owner,
        )

        org_super_power.additional_properties = d
        return org_super_power

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
