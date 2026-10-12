from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgMember")


@_attrs_define
class OrgMember:
    """
    Attributes:
        disabled (bool):
        email (str):
        joined_at (datetime.datetime):
        name (str):
        role (str):
        user_id (UUID):
    """

    disabled: bool
    email: str
    joined_at: datetime.datetime
    name: str
    role: str
    user_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        disabled = self.disabled

        email = self.email

        joined_at = self.joined_at.isoformat()

        name = self.name

        role = self.role

        user_id = str(self.user_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "disabled": disabled,
                "email": email,
                "joined_at": joined_at,
                "name": name,
                "role": role,
                "user_id": user_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        disabled = d.pop("disabled")

        email = d.pop("email")

        joined_at = datetime.datetime.fromisoformat(d.pop("joined_at"))

        name = d.pop("name")

        role = d.pop("role")

        user_id = UUID(d.pop("user_id"))

        org_member = cls(
            disabled=disabled,
            email=email,
            joined_at=joined_at,
            name=name,
            role=role,
            user_id=user_id,
        )

        org_member.additional_properties = d
        return org_member

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
