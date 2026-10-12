from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.schedule_view_input import ScheduleViewInput


T = TypeVar("T", bound="ScheduleView")


@_attrs_define
class ScheduleView:
    """
    Attributes:
        cron (str):
        enabled (bool):
        id (UUID):
        input_ (ScheduleViewInput):
        machine (str):
        machine_id (UUID):
        name (str):
        next_run_at (datetime.datetime | None):
        power_id (None | UUID):
        super_power_id (None | UUID):
        time_zone (str):
    """

    cron: str
    enabled: bool
    id: UUID
    input_: ScheduleViewInput
    machine: str
    machine_id: UUID
    name: str
    next_run_at: datetime.datetime | None
    power_id: UUID | None
    super_power_id: UUID | None
    time_zone: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cron = self.cron

        enabled = self.enabled

        id = str(self.id)

        input_ = self.input_.to_dict()

        machine = self.machine

        machine_id = str(self.machine_id)

        name = self.name

        next_run_at: str | None
        if isinstance(self.next_run_at, datetime.datetime):
            next_run_at = self.next_run_at.isoformat()
        else:
            next_run_at = self.next_run_at

        power_id: str | None
        if isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        super_power_id: str | None
        if isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        time_zone = self.time_zone

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cron": cron,
                "enabled": enabled,
                "id": id,
                "input": input_,
                "machine": machine,
                "machine_id": machine_id,
                "name": name,
                "next_run_at": next_run_at,
                "power_id": power_id,
                "super_power_id": super_power_id,
                "time_zone": time_zone,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.schedule_view_input import ScheduleViewInput

        d = dict(src_dict)
        cron = d.pop("cron")

        enabled = d.pop("enabled")

        id = UUID(d.pop("id"))

        input_ = ScheduleViewInput.from_dict(d.pop("input"))

        machine = d.pop("machine")

        machine_id = UUID(d.pop("machine_id"))

        name = d.pop("name")

        def _parse_next_run_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_run_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_run_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        next_run_at = _parse_next_run_at(d.pop("next_run_at"))

        def _parse_power_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                power_id_type_0 = UUID(data)

                return power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        power_id = _parse_power_id(d.pop("power_id"))

        def _parse_super_power_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                super_power_id_type_0 = UUID(data)

                return super_power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        super_power_id = _parse_super_power_id(d.pop("super_power_id"))

        time_zone = d.pop("time_zone")

        schedule_view = cls(
            cron=cron,
            enabled=enabled,
            id=id,
            input_=input_,
            machine=machine,
            machine_id=machine_id,
            name=name,
            next_run_at=next_run_at,
            power_id=power_id,
            super_power_id=super_power_id,
            time_zone=time_zone,
        )

        schedule_view.additional_properties = d
        return schedule_view

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
