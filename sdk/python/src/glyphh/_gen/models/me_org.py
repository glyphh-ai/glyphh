from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="MeOrg")


@_attrs_define
class MeOrg:
    """
    Attributes:
        id (UUID):
        name (str):
        personal (bool):
        plan (str):
        role (str):
    """

    id: UUID
    name: str
    personal: bool
    plan: str
    role: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        name = self.name

        personal = self.personal

        plan = self.plan

        role = self.role

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "personal": personal,
                "plan": plan,
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        name = d.pop("name")

        personal = d.pop("personal")

        plan = d.pop("plan")

        role = d.pop("role")

        me_org = cls(
            id=id,
            name=name,
            personal=personal,
            plan=plan,
            role=role,
        )

        me_org.additional_properties = d
        return me_org

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
