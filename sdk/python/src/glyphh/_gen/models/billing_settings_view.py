from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.settings_row import SettingsRow


T = TypeVar("T", bound="BillingSettingsView")


@_attrs_define
class BillingSettingsView:
    """
    Attributes:
        current (SettingsRow):
        history (list[SettingsRow]):
        upcoming (list[SettingsRow]):
    """

    current: SettingsRow
    history: list[SettingsRow]
    upcoming: list[SettingsRow]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        current = self.current.to_dict()

        history = []
        for history_item_data in self.history:
            history_item = history_item_data.to_dict()
            history.append(history_item)

        upcoming = []
        for upcoming_item_data in self.upcoming:
            upcoming_item = upcoming_item_data.to_dict()
            upcoming.append(upcoming_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "current": current,
                "history": history,
                "upcoming": upcoming,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.settings_row import SettingsRow

        d = dict(src_dict)
        current = SettingsRow.from_dict(d.pop("current"))

        history = []
        _history = d.pop("history")
        for history_item_data in _history:
            history_item = SettingsRow.from_dict(history_item_data)

            history.append(history_item)

        upcoming = []
        _upcoming = d.pop("upcoming")
        for upcoming_item_data in _upcoming:
            upcoming_item = SettingsRow.from_dict(upcoming_item_data)

            upcoming.append(upcoming_item)

        billing_settings_view = cls(
            current=current,
            history=history,
            upcoming=upcoming,
        )

        billing_settings_view.additional_properties = d
        return billing_settings_view

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
