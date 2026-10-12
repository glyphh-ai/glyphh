from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.listing_change_reach_type_0 import ListingChangeReachType0
from ..types import UNSET, Unset

T = TypeVar("T", bound="ListingChange")


@_attrs_define
class ListingChange:
    """
    Attributes:
        category (None | str | Unset):
        description (None | str | Unset):
        name (None | str | Unset):
        reach (ListingChangeReachType0 | None | Unset):
        summary (None | str | Unset):
    """

    category: str | Unset | None = UNSET
    description: str | Unset | None = UNSET
    name: str | Unset | None = UNSET
    reach: ListingChangeReachType0 | Unset | None = UNSET
    summary: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        category: str | Unset | None
        if isinstance(self.category, Unset):
            category = UNSET
        else:
            category = self.category

        description: str | Unset | None
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        reach: str | Unset | None
        if isinstance(self.reach, Unset):
            reach = UNSET
        elif isinstance(self.reach, ListingChangeReachType0):
            reach = self.reach.value
        else:
            reach = self.reach

        summary: str | Unset | None
        if isinstance(self.summary, Unset):
            summary = UNSET
        else:
            summary = self.summary

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if category is not UNSET:
            field_dict["category"] = category
        if description is not UNSET:
            field_dict["description"] = description
        if name is not UNSET:
            field_dict["name"] = name
        if reach is not UNSET:
            field_dict["reach"] = reach
        if summary is not UNSET:
            field_dict["summary"] = summary

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_category(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        category = _parse_category(d.pop("category", UNSET))

        def _parse_description(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_reach(data: object) -> ListingChangeReachType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                reach_type_0 = ListingChangeReachType0(data)

                return reach_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ListingChangeReachType0 | None | Unset, data)

        reach = _parse_reach(d.pop("reach", UNSET))

        def _parse_summary(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        summary = _parse_summary(d.pop("summary", UNSET))

        listing_change = cls(
            category=category,
            description=description,
            name=name,
            reach=reach,
            summary=summary,
        )

        listing_change.additional_properties = d
        return listing_change

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
