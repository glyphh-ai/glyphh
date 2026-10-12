from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.balance import Balance
    from ..models.day import Day
    from ..models.span import Span
    from ..models.tiles import Tiles


T = TypeVar("T", bound="UsagePage")


@_attrs_define
class UsagePage:
    """
    Attributes:
        balance (Balance):
        days (list[Day]):
        span (Span):
        tiles (Tiles):
    """

    balance: Balance
    days: list[Day]
    span: Span
    tiles: Tiles
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        balance = self.balance.to_dict()

        days = []
        for days_item_data in self.days:
            days_item = days_item_data.to_dict()
            days.append(days_item)

        span = self.span.to_dict()

        tiles = self.tiles.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "balance": balance,
                "days": days,
                "span": span,
                "tiles": tiles,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.balance import Balance
        from ..models.day import Day
        from ..models.span import Span
        from ..models.tiles import Tiles

        d = dict(src_dict)
        balance = Balance.from_dict(d.pop("balance"))

        days = []
        _days = d.pop("days")
        for days_item_data in _days:
            days_item = Day.from_dict(days_item_data)

            days.append(days_item)

        span = Span.from_dict(d.pop("span"))

        tiles = Tiles.from_dict(d.pop("tiles"))

        usage_page = cls(
            balance=balance,
            days=days,
            span=span,
            tiles=tiles,
        )

        usage_page.additional_properties = d
        return usage_page

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
