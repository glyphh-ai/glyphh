from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.tool_permission import ToolPermission
from ..models.tool_risk import ToolRisk

if TYPE_CHECKING:
    from ..models.override import Override


T = TypeVar("T", bound="Tool")


@_attrs_define
class Tool:
    """
    Attributes:
        description (str):
        name (str):
        overrides (list[Override]):
        permission (ToolPermission):
        risk (ToolRisk):
        tool (str):
    """

    description: str
    name: str
    overrides: list[Override]
    permission: ToolPermission
    risk: ToolRisk
    tool: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        name = self.name

        overrides = []
        for overrides_item_data in self.overrides:
            overrides_item = overrides_item_data.to_dict()
            overrides.append(overrides_item)

        permission = self.permission.value

        risk = self.risk.value

        tool = self.tool

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "description": description,
                "name": name,
                "overrides": overrides,
                "permission": permission,
                "risk": risk,
                "tool": tool,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.override import Override

        d = dict(src_dict)
        description = d.pop("description")

        name = d.pop("name")

        overrides = []
        _overrides = d.pop("overrides")
        for overrides_item_data in _overrides:
            overrides_item = Override.from_dict(overrides_item_data)

            overrides.append(overrides_item)

        permission = ToolPermission(d.pop("permission"))

        risk = ToolRisk(d.pop("risk"))

        tool = d.pop("tool")

        tool = cls(
            description=description,
            name=name,
            overrides=overrides,
            permission=permission,
            risk=risk,
            tool=tool,
        )

        tool.additional_properties = d
        return tool

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
