from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="InviteView")


@_attrs_define
class InviteView:
    """
    Attributes:
        email (str):
        expires_at (datetime.datetime):
        id (UUID):
        role (str):
    """

    email: str
    expires_at: datetime.datetime
    id: UUID
    role: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        expires_at = self.expires_at.isoformat()

        id = str(self.id)

        role = self.role

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "expires_at": expires_at,
                "id": id,
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        id = UUID(d.pop("id"))

        role = d.pop("role")

        invite_view = cls(
            email=email,
            expires_at=expires_at,
            id=id,
            role=role,
        )

        invite_view.additional_properties = d
        return invite_view

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
