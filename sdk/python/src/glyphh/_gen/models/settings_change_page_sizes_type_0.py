from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.settings_change_page_sizes_type_0_additional_property import (
    SettingsChangePageSizesType0AdditionalProperty,
)

T = TypeVar("T", bound="SettingsChangePageSizesType0")


@_attrs_define
class SettingsChangePageSizesType0:
    additional_properties: dict[str, SettingsChangePageSizesType0AdditionalProperty] = (
        _attrs_field(init=False, factory=dict)
    )

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop.value

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        settings_change_page_sizes_type_0 = cls()

        additional_properties = {}
        for prop_name, prop_dict in d.items():
            additional_property = SettingsChangePageSizesType0AdditionalProperty(
                prop_dict
            )

            additional_properties[prop_name] = additional_property

        settings_change_page_sizes_type_0.additional_properties = additional_properties
        return settings_change_page_sizes_type_0

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> SettingsChangePageSizesType0AdditionalProperty:
        return self.additional_properties[key]

    def __setitem__(
        self, key: str, value: SettingsChangePageSizesType0AdditionalProperty
    ) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
