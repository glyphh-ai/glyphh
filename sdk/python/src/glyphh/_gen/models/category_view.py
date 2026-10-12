from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CategoryView")


@_attrs_define
class CategoryView:
    """
    Attributes:
        id (UUID):
        listings (int):
        name (str):
        slug (str):
        sort (int):
    """

    id: UUID
    listings: int
    name: str
    slug: str
    sort: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        listings = self.listings

        name = self.name

        slug = self.slug

        sort = self.sort

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "listings": listings,
                "name": name,
                "slug": slug,
                "sort": sort,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        listings = d.pop("listings")

        name = d.pop("name")

        slug = d.pop("slug")

        sort = d.pop("sort")

        category_view = cls(
            id=id,
            listings=listings,
            name=name,
            slug=slug,
            sort=sort,
        )

        category_view.additional_properties = d
        return category_view

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
