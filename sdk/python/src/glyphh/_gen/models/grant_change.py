from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.grant_change_access_type_0 import GrantChangeAccessType0
from ..types import UNSET, Unset

T = TypeVar("T", bound="GrantChange")


@_attrs_define
class GrantChange:
    """One thing to give or take away: exactly one of a power, a machine or another super power.

    Attributes:
        access (GrantChangeAccessType0 | None | Unset):
        granted (bool | Unset):  Default: True.
        machine_id (None | Unset | UUID):
        power_id (None | Unset | UUID):
        super_power_id (None | Unset | UUID):
    """

    access: GrantChangeAccessType0 | Unset | None = UNSET
    granted: bool | Unset = True
    machine_id: Unset | UUID | None = UNSET
    power_id: Unset | UUID | None = UNSET
    super_power_id: Unset | UUID | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access: str | Unset | None
        if isinstance(self.access, Unset):
            access = UNSET
        elif isinstance(self.access, GrantChangeAccessType0):
            access = self.access.value
        else:
            access = self.access

        granted = self.granted

        machine_id: str | Unset | None
        if isinstance(self.machine_id, Unset):
            machine_id = UNSET
        elif isinstance(self.machine_id, UUID):
            machine_id = str(self.machine_id)
        else:
            machine_id = self.machine_id

        power_id: str | Unset | None
        if isinstance(self.power_id, Unset):
            power_id = UNSET
        elif isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        super_power_id: str | Unset | None
        if isinstance(self.super_power_id, Unset):
            super_power_id = UNSET
        elif isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if access is not UNSET:
            field_dict["access"] = access
        if granted is not UNSET:
            field_dict["granted"] = granted
        if machine_id is not UNSET:
            field_dict["machine_id"] = machine_id
        if power_id is not UNSET:
            field_dict["power_id"] = power_id
        if super_power_id is not UNSET:
            field_dict["super_power_id"] = super_power_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_access(data: object) -> GrantChangeAccessType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                access_type_0 = GrantChangeAccessType0(data)

                return access_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(GrantChangeAccessType0 | None | Unset, data)

        access = _parse_access(d.pop("access", UNSET))

        granted = d.pop("granted", UNSET)

        def _parse_machine_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                machine_id_type_0 = UUID(data)

                return machine_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        machine_id = _parse_machine_id(d.pop("machine_id", UNSET))

        def _parse_power_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                power_id_type_0 = UUID(data)

                return power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        power_id = _parse_power_id(d.pop("power_id", UNSET))

        def _parse_super_power_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                super_power_id_type_0 = UUID(data)

                return super_power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        super_power_id = _parse_super_power_id(d.pop("super_power_id", UNSET))

        grant_change = cls(
            access=access,
            granted=granted,
            machine_id=machine_id,
            power_id=power_id,
            super_power_id=super_power_id,
        )

        grant_change.additional_properties = d
        return grant_change

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
