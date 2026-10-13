from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="HostLaunch")


@_attrs_define
class HostLaunch:
    """
    Attributes:
        code (str):
        command (None | str):
        expires_at (datetime.datetime):
        host (str):
        url (None | str):
        user_data (None | str):
    """

    code: str
    command: str | None
    expires_at: datetime.datetime
    host: str
    url: str | None
    user_data: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        command: str | None
        command = self.command

        expires_at = self.expires_at.isoformat()

        host = self.host

        url: str | None
        url = self.url

        user_data: str | None
        user_data = self.user_data

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "code": code,
                "command": command,
                "expires_at": expires_at,
                "host": host,
                "url": url,
                "user_data": user_data,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        code = d.pop("code")

        def _parse_command(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        command = _parse_command(d.pop("command"))

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        host = d.pop("host")

        def _parse_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        url = _parse_url(d.pop("url"))

        def _parse_user_data(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        user_data = _parse_user_data(d.pop("user_data"))

        host_launch = cls(
            code=code,
            command=command,
            expires_at=expires_at,
            host=host,
            url=url,
            user_data=user_data,
        )

        host_launch.additional_properties = d
        return host_launch

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
