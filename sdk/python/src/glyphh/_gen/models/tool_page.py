from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.tool import Tool
    from ..models.tool_page_counts import ToolPageCounts


T = TypeVar("T", bound="ToolPage")


@_attrs_define
class ToolPage:
    """
    Attributes:
        counts (ToolPageCounts):
        tools (list[Tool]):
        total (int):
    """

    counts: ToolPageCounts
    tools: list[Tool]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        counts = self.counts.to_dict()

        tools = []
        for tools_item_data in self.tools:
            tools_item = tools_item_data.to_dict()
            tools.append(tools_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "counts": counts,
                "tools": tools,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.tool import Tool
        from ..models.tool_page_counts import ToolPageCounts

        d = dict(src_dict)
        counts = ToolPageCounts.from_dict(d.pop("counts"))

        tools = []
        _tools = d.pop("tools")
        for tools_item_data in _tools:
            tools_item = Tool.from_dict(tools_item_data)

            tools.append(tools_item)

        total = d.pop("total")

        tool_page = cls(
            counts=counts,
            tools=tools,
            total=total,
        )

        tool_page.additional_properties = d
        return tool_page

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
