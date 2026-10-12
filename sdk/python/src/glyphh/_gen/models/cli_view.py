from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CliView")


@_attrs_define
class CliView:
    """
    Attributes:
        account (None | str):
        cli (str):
        login_error (None | str):
        login_step (str):
        signed_in (bool):
        updated_at (datetime.datetime):
        version (str):
    """

    account: str | None
    cli: str
    login_error: str | None
    login_step: str
    signed_in: bool
    updated_at: datetime.datetime
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account: str | None
        account = self.account

        cli = self.cli

        login_error: str | None
        login_error = self.login_error

        login_step = self.login_step

        signed_in = self.signed_in

        updated_at = self.updated_at.isoformat()

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account": account,
                "cli": cli,
                "login_error": login_error,
                "login_step": login_step,
                "signed_in": signed_in,
                "updated_at": updated_at,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_account(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        account = _parse_account(d.pop("account"))

        cli = d.pop("cli")

        def _parse_login_error(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        login_error = _parse_login_error(d.pop("login_error"))

        login_step = d.pop("login_step")

        signed_in = d.pop("signed_in")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        version = d.pop("version")

        cli_view = cls(
            account=account,
            cli=cli,
            login_error=login_error,
            login_step=login_step,
            signed_in=signed_in,
            updated_at=updated_at,
            version=version,
        )

        cli_view.additional_properties = d
        return cli_view

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
