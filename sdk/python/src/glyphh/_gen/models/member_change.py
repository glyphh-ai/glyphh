from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.member_change_role_type_0 import MemberChangeRoleType0
from ..types import UNSET, Unset

T = TypeVar("T", bound="MemberChange")


@_attrs_define
class MemberChange:
    """
    Attributes:
        disabled (bool | None | Unset):
        role (MemberChangeRoleType0 | None | Unset):
    """

    disabled: bool | None | Unset = UNSET
    role: MemberChangeRoleType0 | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        disabled: bool | None | Unset
        if isinstance(self.disabled, Unset):
            disabled = UNSET
        else:
            disabled = self.disabled

        role: None | str | Unset
        if isinstance(self.role, Unset):
            role = UNSET
        elif isinstance(self.role, MemberChangeRoleType0):
            role = self.role.value
        else:
            role = self.role

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if disabled is not UNSET:
            field_dict["disabled"] = disabled
        if role is not UNSET:
            field_dict["role"] = role

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_disabled(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        disabled = _parse_disabled(d.pop("disabled", UNSET))

        def _parse_role(data: object) -> MemberChangeRoleType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                role_type_0 = MemberChangeRoleType0(data)

                return role_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(MemberChangeRoleType0 | None | Unset, data)

        role = _parse_role(d.pop("role", UNSET))

        member_change = cls(
            disabled=disabled,
            role=role,
        )

        member_change.additional_properties = d
        return member_change

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
