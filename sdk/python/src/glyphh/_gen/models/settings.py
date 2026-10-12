from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.settings_theme import SettingsTheme
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.settings_page_sizes import SettingsPageSizes


T = TypeVar("T", bound="Settings")


@_attrs_define
class Settings:
    """
    Attributes:
        page_sizes (SettingsPageSizes | Unset):
        rail_collapsed (bool | Unset):  Default: False.
        theme (SettingsTheme | Unset):  Default: SettingsTheme.SYSTEM.
    """

    page_sizes: SettingsPageSizes | Unset = UNSET
    rail_collapsed: bool | Unset = False
    theme: SettingsTheme | Unset = SettingsTheme.SYSTEM
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        page_sizes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.page_sizes, Unset):
            page_sizes = self.page_sizes.to_dict()

        rail_collapsed = self.rail_collapsed

        theme: str | Unset = UNSET
        if not isinstance(self.theme, Unset):
            theme = self.theme.value

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
        from ..models.settings_page_sizes import SettingsPageSizes

        d = dict(src_dict)
        _page_sizes = d.pop("page_sizes", UNSET)
        page_sizes: SettingsPageSizes | Unset
        if isinstance(_page_sizes, Unset):
            page_sizes = UNSET
        else:
            page_sizes = SettingsPageSizes.from_dict(_page_sizes)

        rail_collapsed = d.pop("rail_collapsed", UNSET)

        _theme = d.pop("theme", UNSET)
        theme: SettingsTheme | Unset
        if isinstance(_theme, Unset):
            theme = UNSET
        else:
            theme = SettingsTheme(_theme)

        settings = cls(
            page_sizes=page_sizes,
            rail_collapsed=rail_collapsed,
            theme=theme,
        )

        settings.additional_properties = d
        return settings

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
