from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Span")


@_attrs_define
class Span:
    """
    Attributes:
        first (datetime.date):
        last (datetime.date):
        period_end (datetime.datetime):
        period_start (datetime.datetime):
        rolled_through (datetime.date | None):
        today (datetime.date):
        updated_at (datetime.datetime):
    """

    first: datetime.date
    last: datetime.date
    period_end: datetime.datetime
    period_start: datetime.datetime
    rolled_through: datetime.date | None
    today: datetime.date
    updated_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        first = self.first.isoformat()

        last = self.last.isoformat()

        period_end = self.period_end.isoformat()

        period_start = self.period_start.isoformat()

        rolled_through: str | None
        if isinstance(self.rolled_through, datetime.date):
            rolled_through = self.rolled_through.isoformat()
        else:
            rolled_through = self.rolled_through

        today = self.today.isoformat()

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "first": first,
                "last": last,
                "period_end": period_end,
                "period_start": period_start,
                "rolled_through": rolled_through,
                "today": today,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        first = datetime.date.fromisoformat(d.pop("first"))

        last = datetime.date.fromisoformat(d.pop("last"))

        period_end = datetime.datetime.fromisoformat(d.pop("period_end"))

        period_start = datetime.datetime.fromisoformat(d.pop("period_start"))

        def _parse_rolled_through(data: object) -> datetime.date | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                rolled_through_type_0 = datetime.date.fromisoformat(data)

                return rolled_through_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None, data)

        rolled_through = _parse_rolled_through(d.pop("rolled_through"))

        today = datetime.date.fromisoformat(d.pop("today"))

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        span = cls(
            first=first,
            last=last,
            period_end=period_end,
            period_start=period_start,
            rolled_through=rolled_through,
            today=today,
            updated_at=updated_at,
        )

        span.additional_properties = d
        return span

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
