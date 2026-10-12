from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Host")


@_attrs_define
class Host:
    """
    Attributes:
        connected_at (datetime.datetime):
        id (UUID):
        name (str):
        org (None | str): the org it acts in now: its newest sign-in's
    """

    connected_at: datetime.datetime
    id: UUID
    name: str
    org: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        connected_at = self.connected_at.isoformat()

        id = str(self.id)

        name = self.name

        org: str | None
        org = self.org

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "connected_at": connected_at,
                "id": id,
                "name": name,
                "org": org,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        connected_at = datetime.datetime.fromisoformat(d.pop("connected_at"))

        id = UUID(d.pop("id"))

        name = d.pop("name")

        def _parse_org(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        org = _parse_org(d.pop("org"))

        host = cls(
            connected_at=connected_at,
            id=id,
            name=name,
            org=org,
        )

        host.additional_properties = d
        return host

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
