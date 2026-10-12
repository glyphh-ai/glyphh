from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.market_card import MarketCard
    from ..models.market_page_categories import MarketPageCategories
    from ..models.market_page_types import MarketPageTypes


T = TypeVar("T", bound="MarketPage")


@_attrs_define
class MarketPage:
    """
    Attributes:
        categories (MarketPageCategories):
        listings (list[MarketCard]):
        total (int):
        types (MarketPageTypes):
    """

    categories: MarketPageCategories
    listings: list[MarketCard]
    total: int
    types: MarketPageTypes
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        categories = self.categories.to_dict()

        listings = []
        for listings_item_data in self.listings:
            listings_item = listings_item_data.to_dict()
            listings.append(listings_item)

        total = self.total

        types = self.types.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "categories": categories,
                "listings": listings,
                "total": total,
                "types": types,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.market_card import MarketCard
        from ..models.market_page_categories import MarketPageCategories
        from ..models.market_page_types import MarketPageTypes

        d = dict(src_dict)
        categories = MarketPageCategories.from_dict(d.pop("categories"))

        listings = []
        _listings = d.pop("listings")
        for listings_item_data in _listings:
            listings_item = MarketCard.from_dict(listings_item_data)

            listings.append(listings_item)

        total = d.pop("total")

        types = MarketPageTypes.from_dict(d.pop("types"))

        market_page = cls(
            categories=categories,
            listings=listings,
            total=total,
            types=types,
        )

        market_page.additional_properties = d
        return market_page

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
