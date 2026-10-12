from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProviderChange")


@_attrs_define
class ProviderChange:
    """
    Attributes:
        active (bool | None | Unset):
        base_url (None | str | Unset):
        name (None | str | Unset):
        sort (int | None | Unset):
    """

    active: bool | Unset | None = UNSET
    base_url: str | Unset | None = UNSET
    name: str | Unset | None = UNSET
    sort: int | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        active: bool | Unset | None
        if isinstance(self.active, Unset):
            active = UNSET
        else:
            active = self.active

        base_url: str | Unset | None
        if isinstance(self.base_url, Unset):
            base_url = UNSET
        else:
            base_url = self.base_url

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        sort: int | Unset | None
        if isinstance(self.sort, Unset):
            sort = UNSET
        else:
            sort = self.sort

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if active is not UNSET:
            field_dict["active"] = active
        if base_url is not UNSET:
            field_dict["base_url"] = base_url
        if name is not UNSET:
            field_dict["name"] = name
        if sort is not UNSET:
            field_dict["sort"] = sort

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_active(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        active = _parse_active(d.pop("active", UNSET))

        def _parse_base_url(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        base_url = _parse_base_url(d.pop("base_url", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_sort(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        sort = _parse_sort(d.pop("sort", UNSET))

        provider_change = cls(
            active=active,
            base_url=base_url,
            name=name,
            sort=sort,
        )

        provider_change.additional_properties = d
        return provider_change

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
