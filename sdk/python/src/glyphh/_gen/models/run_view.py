from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.run_view_result_type_0 import RunViewResultType0


T = TypeVar("T", bound="RunView")


@_attrs_define
class RunView:
    """
    Attributes:
        calls (int):
        cost_cents (int):
        created_at (datetime.datetime):
        error (None | str):
        finished_at (datetime.datetime | None):
        id (UUID):
        machine (None | str):
        machine_id (None | UUID):
        mode (str):
        power_id (None | UUID):
        result (None | RunViewResultType0):
        schedule (None | str):
        schedule_id (None | UUID):
        scheduled_for (datetime.datetime | None):
        started_at (datetime.datetime | None):
        status (str):
        super_power (None | str):
        super_power_id (None | UUID):
        task (None | str):
        thread_id (None | UUID):
        trigger (str):
    """

    calls: int
    cost_cents: int
    created_at: datetime.datetime
    error: str | None
    finished_at: datetime.datetime | None
    id: UUID
    machine: str | None
    machine_id: UUID | None
    mode: str
    power_id: UUID | None
    result: RunViewResultType0 | None
    schedule: str | None
    schedule_id: UUID | None
    scheduled_for: datetime.datetime | None
    started_at: datetime.datetime | None
    status: str
    super_power: str | None
    super_power_id: UUID | None
    task: str | None
    thread_id: UUID | None
    trigger: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.run_view_result_type_0 import RunViewResultType0

        calls = self.calls

        cost_cents = self.cost_cents

        created_at = self.created_at.isoformat()

        error: str | None
        error = self.error

        finished_at: str | None
        if isinstance(self.finished_at, datetime.datetime):
            finished_at = self.finished_at.isoformat()
        else:
            finished_at = self.finished_at

        id = str(self.id)

        machine: str | None
        machine = self.machine

        machine_id: str | None
        if isinstance(self.machine_id, UUID):
            machine_id = str(self.machine_id)
        else:
            machine_id = self.machine_id

        mode = self.mode

        power_id: str | None
        if isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        result: dict[str, Any] | None
        if isinstance(self.result, RunViewResultType0):
            result = self.result.to_dict()
        else:
            result = self.result

        schedule: str | None
        schedule = self.schedule

        schedule_id: str | None
        if isinstance(self.schedule_id, UUID):
            schedule_id = str(self.schedule_id)
        else:
            schedule_id = self.schedule_id

        scheduled_for: str | None
        if isinstance(self.scheduled_for, datetime.datetime):
            scheduled_for = self.scheduled_for.isoformat()
        else:
            scheduled_for = self.scheduled_for

        started_at: str | None
        if isinstance(self.started_at, datetime.datetime):
            started_at = self.started_at.isoformat()
        else:
            started_at = self.started_at

        status = self.status

        super_power: str | None
        super_power = self.super_power

        super_power_id: str | None
        if isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        task: str | None
        task = self.task

        thread_id: str | None
        if isinstance(self.thread_id, UUID):
            thread_id = str(self.thread_id)
        else:
            thread_id = self.thread_id

        trigger = self.trigger

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "calls": calls,
                "cost_cents": cost_cents,
                "created_at": created_at,
                "error": error,
                "finished_at": finished_at,
                "id": id,
                "machine": machine,
                "machine_id": machine_id,
                "mode": mode,
                "power_id": power_id,
                "result": result,
                "schedule": schedule,
                "schedule_id": schedule_id,
                "scheduled_for": scheduled_for,
                "started_at": started_at,
                "status": status,
                "super_power": super_power,
                "super_power_id": super_power_id,
                "task": task,
                "thread_id": thread_id,
                "trigger": trigger,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.run_view_result_type_0 import RunViewResultType0

        d = dict(src_dict)
        calls = d.pop("calls")

        cost_cents = d.pop("cost_cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_error(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        error = _parse_error(d.pop("error"))

        def _parse_finished_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                finished_at_type_0 = datetime.datetime.fromisoformat(data)

                return finished_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        finished_at = _parse_finished_at(d.pop("finished_at"))

        id = UUID(d.pop("id"))

        def _parse_machine(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        machine = _parse_machine(d.pop("machine"))

        def _parse_machine_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                machine_id_type_0 = UUID(data)

                return machine_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        machine_id = _parse_machine_id(d.pop("machine_id"))

        mode = d.pop("mode")

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

        def _parse_result(data: object) -> RunViewResultType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                result_type_0 = RunViewResultType0.from_dict(data)

                return result_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | RunViewResultType0, data)

        result = _parse_result(d.pop("result"))

        def _parse_schedule(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        schedule = _parse_schedule(d.pop("schedule"))

        def _parse_schedule_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                schedule_id_type_0 = UUID(data)

                return schedule_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        schedule_id = _parse_schedule_id(d.pop("schedule_id"))

        def _parse_scheduled_for(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                scheduled_for_type_0 = datetime.datetime.fromisoformat(data)

                return scheduled_for_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        scheduled_for = _parse_scheduled_for(d.pop("scheduled_for"))

        def _parse_started_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                started_at_type_0 = datetime.datetime.fromisoformat(data)

                return started_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        started_at = _parse_started_at(d.pop("started_at"))

        status = d.pop("status")

        def _parse_super_power(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        super_power = _parse_super_power(d.pop("super_power"))

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

        def _parse_task(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        task = _parse_task(d.pop("task"))

        def _parse_thread_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                thread_id_type_0 = UUID(data)

                return thread_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        thread_id = _parse_thread_id(d.pop("thread_id"))

        trigger = d.pop("trigger")

        run_view = cls(
            calls=calls,
            cost_cents=cost_cents,
            created_at=created_at,
            error=error,
            finished_at=finished_at,
            id=id,
            machine=machine,
            machine_id=machine_id,
            mode=mode,
            power_id=power_id,
            result=result,
            schedule=schedule,
            schedule_id=schedule_id,
            scheduled_for=scheduled_for,
            started_at=started_at,
            status=status,
            super_power=super_power,
            super_power_id=super_power_id,
            task=task,
            thread_id=thread_id,
            trigger=trigger,
        )

        run_view.additional_properties = d
        return run_view

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
