from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.home_categories_item import HomeCategoriesItem
    from ..models.market_card import MarketCard


T = TypeVar("T", bound="Home")


@_attrs_define
class Home:
    """
    Attributes:
        categories (list[HomeCategoriesItem]):
        featured (list[MarketCard]):
        newest (list[MarketCard]):
        popular (list[MarketCard]):
    """

    categories: list[HomeCategoriesItem]
    featured: list[MarketCard]
    newest: list[MarketCard]
    popular: list[MarketCard]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        categories = []
        for categories_item_data in self.categories:
            categories_item = categories_item_data.to_dict()
            categories.append(categories_item)

        featured = []
        for featured_item_data in self.featured:
            featured_item = featured_item_data.to_dict()
            featured.append(featured_item)

        newest = []
        for newest_item_data in self.newest:
            newest_item = newest_item_data.to_dict()
            newest.append(newest_item)

        popular = []
        for popular_item_data in self.popular:
            popular_item = popular_item_data.to_dict()
            popular.append(popular_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "categories": categories,
                "featured": featured,
                "newest": newest,
                "popular": popular,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.home_categories_item import HomeCategoriesItem
        from ..models.market_card import MarketCard

        d = dict(src_dict)
        categories = []
        _categories = d.pop("categories")
        for categories_item_data in _categories:
            categories_item = HomeCategoriesItem.from_dict(categories_item_data)

            categories.append(categories_item)

        featured = []
        _featured = d.pop("featured")
        for featured_item_data in _featured:
            featured_item = MarketCard.from_dict(featured_item_data)

            featured.append(featured_item)

        newest = []
        _newest = d.pop("newest")
        for newest_item_data in _newest:
            newest_item = MarketCard.from_dict(newest_item_data)

            newest.append(newest_item)

        popular = []
        _popular = d.pop("popular")
        for popular_item_data in _popular:
            popular_item = MarketCard.from_dict(popular_item_data)

            popular.append(popular_item)

        home = cls(
            categories=categories,
            featured=featured,
            newest=newest,
            popular=popular,
        )

        home.additional_properties = d
        return home

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
