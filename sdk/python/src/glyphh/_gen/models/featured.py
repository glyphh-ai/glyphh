from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Featured")


@_attrs_define
class Featured:
    """
    Attributes:
        listing_ids (list[UUID]):
    """

    listing_ids: list[UUID]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        listing_ids = []
        for listing_ids_item_data in self.listing_ids:
            listing_ids_item = str(listing_ids_item_data)
            listing_ids.append(listing_ids_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "listing_ids": listing_ids,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        listing_ids = []
        _listing_ids = d.pop("listing_ids")
        for listing_ids_item_data in _listing_ids:
            listing_ids_item = UUID(listing_ids_item_data)

            listing_ids.append(listing_ids_item)

        featured = cls(
            listing_ids=listing_ids,
        )

        featured.additional_properties = d
        return featured

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
