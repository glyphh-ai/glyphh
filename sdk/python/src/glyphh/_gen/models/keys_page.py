from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.key_view import KeyView


T = TypeVar("T", bound="KeysPage")


@_attrs_define
class KeysPage:
    """
    Attributes:
        ask (list[str]): The org admins to ask, when my own keys are off
        keys (list[KeyView]):
        live (int):
        member_keys (bool):
        total (int):
    """

    ask: list[str]
    keys: list[KeyView]
    live: int
    member_keys: bool
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ask = self.ask

        keys = []
        for keys_item_data in self.keys:
            keys_item = keys_item_data.to_dict()
            keys.append(keys_item)

        live = self.live

        member_keys = self.member_keys

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ask": ask,
                "keys": keys,
                "live": live,
                "member_keys": member_keys,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.key_view import KeyView

        d = dict(src_dict)
        ask = cast(list[str], d.pop("ask"))

        keys = []
        _keys = d.pop("keys")
        for keys_item_data in _keys:
            keys_item = KeyView.from_dict(keys_item_data)

            keys.append(keys_item)

        live = d.pop("live")

        member_keys = d.pop("member_keys")

        total = d.pop("total")

        keys_page = cls(
            ask=ask,
            keys=keys,
            live=live,
            member_keys=member_keys,
            total=total,
        )

        keys_page.additional_properties = d
        return keys_page

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
