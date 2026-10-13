from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.relay_tool_input_schema import RelayToolInputSchema


T = TypeVar("T", bound="RelayTool")


@_attrs_define
class RelayTool:
    """
    Attributes:
        description (str):
        input_schema (RelayToolInputSchema):
        name (str):
        permission (str):
        title (None | str):
    """

    description: str
    input_schema: RelayToolInputSchema
    name: str
    permission: str
    title: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        input_schema = self.input_schema.to_dict()

        name = self.name

        permission = self.permission

        title: str | None
        title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "description": description,
                "input_schema": input_schema,
                "name": name,
                "permission": permission,
                "title": title,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.relay_tool_input_schema import RelayToolInputSchema

        d = dict(src_dict)
        description = d.pop("description")

        input_schema = RelayToolInputSchema.from_dict(d.pop("input_schema"))

        name = d.pop("name")

        permission = d.pop("permission")

        def _parse_title(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        title = _parse_title(d.pop("title"))

        relay_tool = cls(
            description=description,
            input_schema=input_schema,
            name=name,
            permission=permission,
            title=title,
        )

        relay_tool.additional_properties = d
        return relay_tool

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
