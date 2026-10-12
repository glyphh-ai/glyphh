from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CategoryOrder")


@_attrs_define
class CategoryOrder:
    """
    Attributes:
        category_ids (list[UUID]):
    """

    category_ids: list[UUID]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        category_ids = []
        for category_ids_item_data in self.category_ids:
            category_ids_item = str(category_ids_item_data)
            category_ids.append(category_ids_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "category_ids": category_ids,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        category_ids = []
        _category_ids = d.pop("category_ids")
        for category_ids_item_data in _category_ids:
            category_ids_item = UUID(category_ids_item_data)

            category_ids.append(category_ids_item)

        category_order = cls(
            category_ids=category_ids,
        )

        category_order.additional_properties = d
        return category_order

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
