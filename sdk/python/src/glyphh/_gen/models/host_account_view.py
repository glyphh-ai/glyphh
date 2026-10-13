from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="HostAccountView")


@_attrs_define
class HostAccountView:
    """
    Attributes:
        account (str):
        checked_at (datetime.datetime | None):
        host (str):
        id (UUID):
        token_last4 (str):
        updated_at (datetime.datetime):
    """

    account: str
    checked_at: datetime.datetime | None
    host: str
    id: UUID
    token_last4: str
    updated_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account = self.account

        checked_at: str | None
        if isinstance(self.checked_at, datetime.datetime):
            checked_at = self.checked_at.isoformat()
        else:
            checked_at = self.checked_at

        host = self.host

        id = str(self.id)

        token_last4 = self.token_last4

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account": account,
                "checked_at": checked_at,
                "host": host,
                "id": id,
                "token_last4": token_last4,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        account = d.pop("account")

        def _parse_checked_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                checked_at_type_0 = datetime.datetime.fromisoformat(data)

                return checked_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        checked_at = _parse_checked_at(d.pop("checked_at"))

        host = d.pop("host")

        id = UUID(d.pop("id"))

        token_last4 = d.pop("token_last4")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        host_account_view = cls(
            account=account,
            checked_at=checked_at,
            host=host,
            id=id,
            token_last4=token_last4,
            updated_at=updated_at,
        )

        host_account_view.additional_properties = d
        return host_account_view

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
