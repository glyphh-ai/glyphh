from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.settings_change_theme_type_0 import SettingsChangeThemeType0
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.settings_change_page_sizes_type_0 import SettingsChangePageSizesType0


T = TypeVar("T", bound="SettingsChange")


@_attrs_define
class SettingsChange:
    """
    Attributes:
        page_sizes (None | SettingsChangePageSizesType0 | Unset):
        rail_collapsed (bool | None | Unset):
        theme (None | SettingsChangeThemeType0 | Unset):
    """

    page_sizes: SettingsChangePageSizesType0 | Unset | None = UNSET
    rail_collapsed: bool | Unset | None = UNSET
    theme: SettingsChangeThemeType0 | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.settings_change_page_sizes_type_0 import SettingsChangePageSizesType0

        page_sizes: dict[str, Any] | Unset | None
        if isinstance(self.page_sizes, Unset):
            page_sizes = UNSET
        elif isinstance(self.page_sizes, SettingsChangePageSizesType0):
            page_sizes = self.page_sizes.to_dict()
        else:
            page_sizes = self.page_sizes

        rail_collapsed: bool | Unset | None
        if isinstance(self.rail_collapsed, Unset):
            rail_collapsed = UNSET
        else:
            rail_collapsed = self.rail_collapsed

        theme: str | Unset | None
        if isinstance(self.theme, Unset):
            theme = UNSET
        elif isinstance(self.theme, SettingsChangeThemeType0):
            theme = self.theme.value
        else:
            theme = self.theme

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if page_sizes is not UNSET:
            field_dict["page_sizes"] = page_sizes
        if rail_collapsed is not UNSET:
            field_dict["rail_collapsed"] = rail_collapsed
        if theme is not UNSET:
            field_dict["theme"] = theme

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.settings_change_page_sizes_type_0 import SettingsChangePageSizesType0

        d = dict(src_dict)

        def _parse_page_sizes(data: object) -> SettingsChangePageSizesType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                page_sizes_type_0 = SettingsChangePageSizesType0.from_dict(data)

                return page_sizes_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SettingsChangePageSizesType0 | Unset, data)

        page_sizes = _parse_page_sizes(d.pop("page_sizes", UNSET))

        def _parse_rail_collapsed(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        rail_collapsed = _parse_rail_collapsed(d.pop("rail_collapsed", UNSET))

        def _parse_theme(data: object) -> SettingsChangeThemeType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                theme_type_0 = SettingsChangeThemeType0(data)

                return theme_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SettingsChangeThemeType0 | Unset, data)

        theme = _parse_theme(d.pop("theme", UNSET))

        settings_change = cls(
            page_sizes=page_sizes,
            rail_collapsed=rail_collapsed,
            theme=theme,
        )

        settings_change.additional_properties = d
        return settings_change

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
