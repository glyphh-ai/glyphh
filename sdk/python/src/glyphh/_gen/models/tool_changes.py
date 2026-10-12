from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.tool_change import ToolChange


T = TypeVar("T", bound="ToolChanges")


@_attrs_define
class ToolChanges:
    """
    Attributes:
        changes (list[ToolChange]):
    """

    changes: list[ToolChange]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        changes = []
        for changes_item_data in self.changes:
            changes_item = changes_item_data.to_dict()
            changes.append(changes_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "changes": changes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.tool_change import ToolChange

        d = dict(src_dict)
        changes = []
        _changes = d.pop("changes")
        for changes_item_data in _changes:
            changes_item = ToolChange.from_dict(changes_item_data)

            changes.append(changes_item)

        tool_changes = cls(
            changes=changes,
        )

        tool_changes.additional_properties = d
        return tool_changes

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
