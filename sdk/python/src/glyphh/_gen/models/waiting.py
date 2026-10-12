from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Waiting")


@_attrs_define
class Waiting:
    """A machine waiting for the member's yes, as the Approve a code page shows it.

    Attributes:
        expires_at (datetime.datetime):
        fingerprint (str):
        host (str):
        name (str):
        platform (str):
        user_code (str):
    """

    expires_at: datetime.datetime
    fingerprint: str
    host: str
    name: str
    platform: str
    user_code: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        expires_at = self.expires_at.isoformat()

        fingerprint = self.fingerprint

        host = self.host

        name = self.name

        platform = self.platform

        user_code = self.user_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "expires_at": expires_at,
                "fingerprint": fingerprint,
                "host": host,
                "name": name,
                "platform": platform,
                "user_code": user_code,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        fingerprint = d.pop("fingerprint")

        host = d.pop("host")

        name = d.pop("name")

        platform = d.pop("platform")

        user_code = d.pop("user_code")

        waiting = cls(
            expires_at=expires_at,
            fingerprint=fingerprint,
            host=host,
            name=name,
            platform=platform,
            user_code=user_code,
        )

        waiting.additional_properties = d
        return waiting

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
