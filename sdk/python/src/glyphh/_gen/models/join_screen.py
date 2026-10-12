from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.join_screen_role import JoinScreenRole

T = TypeVar("T", bound="JoinScreen")


@_attrs_define
class JoinScreen:
    """
    Attributes:
        email (str):
        expires_at (datetime.datetime):
        invited_by (None | str):
        invited_by_email (None | str):
        org (str):
        providers (list[str]):
        role (JoinScreenRole):
    """

    email: str
    expires_at: datetime.datetime
    invited_by: None | str
    invited_by_email: None | str
    org: str
    providers: list[str]
    role: JoinScreenRole
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        expires_at = self.expires_at.isoformat()

        invited_by: None | str
        invited_by = self.invited_by

        invited_by_email: None | str
        invited_by_email = self.invited_by_email

        org = self.org

        providers = self.providers

        role = self.role.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "expires_at": expires_at,
                "invited_by": invited_by,
                "invited_by_email": invited_by_email,
                "org": org,
                "providers": providers,
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        email = d.pop("email")

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        def _parse_invited_by(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        invited_by = _parse_invited_by(d.pop("invited_by"))

        def _parse_invited_by_email(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        invited_by_email = _parse_invited_by_email(d.pop("invited_by_email"))

        org = d.pop("org")

        providers = cast(list[str], d.pop("providers"))

        role = JoinScreenRole(d.pop("role"))

        join_screen = cls(
            email=email,
            expires_at=expires_at,
            invited_by=invited_by,
            invited_by_email=invited_by_email,
            org=org,
            providers=providers,
            role=role,
        )

        join_screen.additional_properties = d
        return join_screen

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
