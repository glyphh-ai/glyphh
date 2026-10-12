from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Balance")


@_attrs_define
class Balance:
    """
    Attributes:
        ask (list[str]):
        balance_cents (int):
        bought_cents (int):
        included_cents (int):
        next_expiry_at (datetime.datetime | None):
        next_expiry_cents (int | None):
        out (bool):
        period_end (datetime.datetime):
        period_start (datetime.datetime):
        used_cents (int):
    """

    ask: list[str]
    balance_cents: int
    bought_cents: int
    included_cents: int
    next_expiry_at: datetime.datetime | None
    next_expiry_cents: int | None
    out: bool
    period_end: datetime.datetime
    period_start: datetime.datetime
    used_cents: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ask = self.ask

        balance_cents = self.balance_cents

        bought_cents = self.bought_cents

        included_cents = self.included_cents

        next_expiry_at: str | None
        if isinstance(self.next_expiry_at, datetime.datetime):
            next_expiry_at = self.next_expiry_at.isoformat()
        else:
            next_expiry_at = self.next_expiry_at

        next_expiry_cents: int | None
        next_expiry_cents = self.next_expiry_cents

        out = self.out

        period_end = self.period_end.isoformat()

        period_start = self.period_start.isoformat()

        used_cents = self.used_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ask": ask,
                "balance_cents": balance_cents,
                "bought_cents": bought_cents,
                "included_cents": included_cents,
                "next_expiry_at": next_expiry_at,
                "next_expiry_cents": next_expiry_cents,
                "out": out,
                "period_end": period_end,
                "period_start": period_start,
                "used_cents": used_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ask = cast(list[str], d.pop("ask"))

        balance_cents = d.pop("balance_cents")

        bought_cents = d.pop("bought_cents")

        included_cents = d.pop("included_cents")

        def _parse_next_expiry_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_expiry_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_expiry_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        next_expiry_at = _parse_next_expiry_at(d.pop("next_expiry_at"))

        def _parse_next_expiry_cents(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        next_expiry_cents = _parse_next_expiry_cents(d.pop("next_expiry_cents"))

        out = d.pop("out")

        period_end = datetime.datetime.fromisoformat(d.pop("period_end"))

        period_start = datetime.datetime.fromisoformat(d.pop("period_start"))

        used_cents = d.pop("used_cents")

        balance = cls(
            ask=ask,
            balance_cents=balance_cents,
            bought_cents=bought_cents,
            included_cents=included_cents,
            next_expiry_at=next_expiry_at,
            next_expiry_cents=next_expiry_cents,
            out=out,
            period_end=period_end,
            period_start=period_start,
            used_cents=used_cents,
        )

        balance.additional_properties = d
        return balance

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
