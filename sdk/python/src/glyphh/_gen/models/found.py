from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.hit import Hit
    from ..models.searched import Searched


T = TypeVar("T", bound="Found")


@_attrs_define
class Found:
    """
    Attributes:
        hits (list[Hit]):
        searched (list[Searched]):
    """

    hits: list[Hit]
    searched: list[Searched]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        hits = []
        for hits_item_data in self.hits:
            hits_item = hits_item_data.to_dict()
            hits.append(hits_item)

        searched = []
        for searched_item_data in self.searched:
            searched_item = searched_item_data.to_dict()
            searched.append(searched_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "hits": hits,
                "searched": searched,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.hit import Hit
        from ..models.searched import Searched

        d = dict(src_dict)
        hits = []
        _hits = d.pop("hits")
        for hits_item_data in _hits:
            hits_item = Hit.from_dict(hits_item_data)

            hits.append(hits_item)

        searched = []
        _searched = d.pop("searched")
        for searched_item_data in _searched:
            searched_item = Searched.from_dict(searched_item_data)

            searched.append(searched_item)

        found = cls(
            hits=hits,
            searched=searched,
        )

        found.additional_properties = d
        return found

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
