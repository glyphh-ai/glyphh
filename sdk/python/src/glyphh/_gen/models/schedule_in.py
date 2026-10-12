from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.schedule_in_input import ScheduleInInput


T = TypeVar("T", bound="ScheduleIn")


@_attrs_define
class ScheduleIn:
    """A schedule for exactly one of a super power or a task.

    Attributes:
        cron (str):
        machine_id (UUID):
        name (str):
        enabled (bool | Unset):  Default: True.
        input_ (ScheduleInInput | Unset):
        power_id (None | Unset | UUID):
        super_power_id (None | Unset | UUID):
        time_zone (str | Unset):  Default: 'UTC'.
    """

    cron: str
    machine_id: UUID
    name: str
    enabled: bool | Unset = True
    input_: ScheduleInInput | Unset = UNSET
    power_id: Unset | UUID | None = UNSET
    super_power_id: Unset | UUID | None = UNSET
    time_zone: str | Unset = "UTC"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cron = self.cron

        machine_id = str(self.machine_id)

        name = self.name

        enabled = self.enabled

        input_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.input_, Unset):
            input_ = self.input_.to_dict()

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

        time_zone = self.time_zone

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cron": cron,
                "machine_id": machine_id,
                "name": name,
            }
        )
        if enabled is not UNSET:
            field_dict["enabled"] = enabled
        if input_ is not UNSET:
            field_dict["input"] = input_
        if power_id is not UNSET:
            field_dict["power_id"] = power_id
        if super_power_id is not UNSET:
            field_dict["super_power_id"] = super_power_id
        if time_zone is not UNSET:
            field_dict["time_zone"] = time_zone

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.schedule_in_input import ScheduleInInput

        d = dict(src_dict)
        cron = d.pop("cron")

        machine_id = UUID(d.pop("machine_id"))

        name = d.pop("name")

        enabled = d.pop("enabled", UNSET)

        _input_ = d.pop("input", UNSET)
        input_: ScheduleInInput | Unset
        if isinstance(_input_, Unset):
            input_ = UNSET
        else:
            input_ = ScheduleInInput.from_dict(_input_)

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

        time_zone = d.pop("time_zone", UNSET)

        schedule_in = cls(
            cron=cron,
            machine_id=machine_id,
            name=name,
            enabled=enabled,
            input_=input_,
            power_id=power_id,
            super_power_id=super_power_id,
            time_zone=time_zone,
        )

        schedule_in.additional_properties = d
        return schedule_in

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
