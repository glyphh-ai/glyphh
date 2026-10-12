from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Asked")


@_attrs_define
class Asked:
    """
    Attributes:
        code (str):
        expires_at (datetime.datetime):
        interval_seconds (int):
        user_code (str):
        verify_url (str):
    """

    code: str
    expires_at: datetime.datetime
    interval_seconds: int
    user_code: str
    verify_url: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        expires_at = self.expires_at.isoformat()

        interval_seconds = self.interval_seconds

        user_code = self.user_code

        verify_url = self.verify_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "code": code,
                "expires_at": expires_at,
                "interval_seconds": interval_seconds,
                "user_code": user_code,
                "verify_url": verify_url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        code = d.pop("code")

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        interval_seconds = d.pop("interval_seconds")

        user_code = d.pop("user_code")

        verify_url = d.pop("verify_url")

        asked = cls(
            code=code,
            expires_at=expires_at,
            interval_seconds=interval_seconds,
            user_code=user_code,
            verify_url=verify_url,
        )

        asked.additional_properties = d
        return asked

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
