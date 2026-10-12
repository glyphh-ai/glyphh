from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.allowed_item import AllowedItem


T = TypeVar("T", bound="AllowedKind")


@_attrs_define
class AllowedKind:
    """
    Attributes:
        items (list[AllowedItem]):
        limited (bool):
        org_count (int):
        org_limits (bool):
    """

    items: list[AllowedItem]
    limited: bool
    org_count: int
    org_limits: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        limited = self.limited

        org_count = self.org_count

        org_limits = self.org_limits

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "items": items,
                "limited": limited,
                "org_count": org_count,
                "org_limits": org_limits,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.allowed_item import AllowedItem

        d = dict(src_dict)
        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = AllowedItem.from_dict(items_item_data)

            items.append(items_item)

        limited = d.pop("limited")

        org_count = d.pop("org_count")

        org_limits = d.pop("org_limits")

        allowed_kind = cls(
            items=items,
            limited=limited,
            org_count=org_count,
            org_limits=org_limits,
        )

        allowed_kind.additional_properties = d
        return allowed_kind

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
