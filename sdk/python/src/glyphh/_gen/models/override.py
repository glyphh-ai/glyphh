from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.override_permission import OverridePermission

T = TypeVar("T", bound="Override")


@_attrs_define
class Override:
    """
    Attributes:
        permission (OverridePermission):
        super_power (str):
        super_power_id (UUID):
    """

    permission: OverridePermission
    super_power: str
    super_power_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        permission = self.permission.value

        super_power = self.super_power

        super_power_id = str(self.super_power_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "permission": permission,
                "super_power": super_power,
                "super_power_id": super_power_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        permission = OverridePermission(d.pop("permission"))

        super_power = d.pop("super_power")

        super_power_id = UUID(d.pop("super_power_id"))

        override = cls(
            permission=permission,
            super_power=super_power,
            super_power_id=super_power_id,
        )

        override.additional_properties = d
        return override

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
