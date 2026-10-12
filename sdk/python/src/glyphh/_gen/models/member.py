from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Member")


@_attrs_define
class Member:
    """
    Attributes:
        disabled (bool):
        email (str):
        first_name (None | str):
        id (UUID):
        joined_at (datetime.datetime):
        last_name (None | str):
        role (str):
    """

    disabled: bool
    email: str
    first_name: None | str
    id: UUID
    joined_at: datetime.datetime
    last_name: None | str
    role: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        disabled = self.disabled

        email = self.email

        first_name: None | str
        first_name = self.first_name

        id = str(self.id)

        joined_at = self.joined_at.isoformat()

        last_name: None | str
        last_name = self.last_name

        role = self.role

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "disabled": disabled,
                "email": email,
                "first_name": first_name,
                "id": id,
                "joined_at": joined_at,
                "last_name": last_name,
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        disabled = d.pop("disabled")

        email = d.pop("email")

        def _parse_first_name(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        first_name = _parse_first_name(d.pop("first_name"))

        id = UUID(d.pop("id"))

        joined_at = datetime.datetime.fromisoformat(d.pop("joined_at"))

        def _parse_last_name(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_name = _parse_last_name(d.pop("last_name"))

        role = d.pop("role")

        member = cls(
            disabled=disabled,
            email=email,
            first_name=first_name,
            id=id,
            joined_at=joined_at,
            last_name=last_name,
            role=role,
        )

        member.additional_properties = d
        return member

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
