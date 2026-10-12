from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AutoTopUp")


@_attrs_define
class AutoTopUp:
    """
    Attributes:
        below_cents (int | None):
        failed_at (datetime.datetime | None):
        failure (None | str):
        last_at (datetime.datetime | None):
        monthly_cap_cents (int | None):
        on (bool):
        to_cents (int | None):
    """

    below_cents: int | None
    failed_at: datetime.datetime | None
    failure: str | None
    last_at: datetime.datetime | None
    monthly_cap_cents: int | None
    on: bool
    to_cents: int | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        below_cents: int | None
        below_cents = self.below_cents

        failed_at: str | None
        if isinstance(self.failed_at, datetime.datetime):
            failed_at = self.failed_at.isoformat()
        else:
            failed_at = self.failed_at

        failure: str | None
        failure = self.failure

        last_at: str | None
        if isinstance(self.last_at, datetime.datetime):
            last_at = self.last_at.isoformat()
        else:
            last_at = self.last_at

        monthly_cap_cents: int | None
        monthly_cap_cents = self.monthly_cap_cents

        on = self.on

        to_cents: int | None
        to_cents = self.to_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "below_cents": below_cents,
                "failed_at": failed_at,
                "failure": failure,
                "last_at": last_at,
                "monthly_cap_cents": monthly_cap_cents,
                "on": on,
                "to_cents": to_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_below_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        below_cents = _parse_below_cents(d.pop("below_cents"))

        def _parse_failed_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                failed_at_type_0 = datetime.datetime.fromisoformat(data)

                return failed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        failed_at = _parse_failed_at(d.pop("failed_at"))

        def _parse_failure(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        failure = _parse_failure(d.pop("failure"))

        def _parse_last_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_at = _parse_last_at(d.pop("last_at"))

        def _parse_monthly_cap_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        monthly_cap_cents = _parse_monthly_cap_cents(d.pop("monthly_cap_cents"))

        on = d.pop("on")

        def _parse_to_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        to_cents = _parse_to_cents(d.pop("to_cents"))

        auto_top_up = cls(
            below_cents=below_cents,
            failed_at=failed_at,
            failure=failure,
            last_at=last_at,
            monthly_cap_cents=monthly_cap_cents,
            on=on,
            to_cents=to_cents,
        )

        auto_top_up.additional_properties = d
        return auto_top_up

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
