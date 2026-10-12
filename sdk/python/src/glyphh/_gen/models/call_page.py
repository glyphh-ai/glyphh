from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.call import Call


T = TypeVar("T", bound="CallPage")


@_attrs_define
class CallPage:
    """
    Attributes:
        calls (list[Call]):
        next_ (None | str):
        total (int):
    """

    calls: list[Call]
    next_: str | None
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        calls = []
        for calls_item_data in self.calls:
            calls_item = calls_item_data.to_dict()
            calls.append(calls_item)

        next_: str | None
        next_ = self.next_

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "calls": calls,
                "next": next_,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.call import Call

        d = dict(src_dict)
        calls = []
        _calls = d.pop("calls")
        for calls_item_data in _calls:
            calls_item = Call.from_dict(calls_item_data)

            calls.append(calls_item)

        def _parse_next_(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        next_ = _parse_next_(d.pop("next"))

        total = d.pop("total")

        call_page = cls(
            calls=calls,
            next_=next_,
            total=total,
        )

        call_page.additional_properties = d
        return call_page

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
