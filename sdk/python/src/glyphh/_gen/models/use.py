from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Use")


@_attrs_define
class Use:
    """
    Attributes:
        cached_tokens (int):
        created_at (datetime.datetime):
        duration_ms (int):
        error_code (None | str):
        event_id (str):
        id (UUID):
        input_tokens (int):
        kind (str):
        machine (None | str):
        machine_id (UUID):
        model (None | str):
        output_tokens (int):
        power (None | str):
        power_id (None | UUID):
        power_kind (None | str):
        run_id (None | UUID):
        started_at (datetime.datetime):
        status (str):
        super_power (None | str):
        super_power_id (None | UUID):
        tool (None | str):
        user (None | str):
        user_id (UUID):
    """

    cached_tokens: int
    created_at: datetime.datetime
    duration_ms: int
    error_code: str | None
    event_id: str
    id: UUID
    input_tokens: int
    kind: str
    machine: str | None
    machine_id: UUID
    model: str | None
    output_tokens: int
    power: str | None
    power_id: UUID | None
    power_kind: str | None
    run_id: UUID | None
    started_at: datetime.datetime
    status: str
    super_power: str | None
    super_power_id: UUID | None
    tool: str | None
    user: str | None
    user_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cached_tokens = self.cached_tokens

        created_at = self.created_at.isoformat()

        duration_ms = self.duration_ms

        error_code: str | None
        error_code = self.error_code

        event_id = self.event_id

        id = str(self.id)

        input_tokens = self.input_tokens

        kind = self.kind

        machine: str | None
        machine = self.machine

        machine_id = str(self.machine_id)

        model: str | None
        model = self.model

        output_tokens = self.output_tokens

        power: str | None
        power = self.power

        power_id: str | None
        if isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        power_kind: str | None
        power_kind = self.power_kind

        run_id: str | None
        if isinstance(self.run_id, UUID):
            run_id = str(self.run_id)
        else:
            run_id = self.run_id

        started_at = self.started_at.isoformat()

        status = self.status

        super_power: str | None
        super_power = self.super_power

        super_power_id: str | None
        if isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        tool: str | None
        tool = self.tool

        user: str | None
        user = self.user

        user_id = str(self.user_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cached_tokens": cached_tokens,
                "created_at": created_at,
                "duration_ms": duration_ms,
                "error_code": error_code,
                "event_id": event_id,
                "id": id,
                "input_tokens": input_tokens,
                "kind": kind,
                "machine": machine,
                "machine_id": machine_id,
                "model": model,
                "output_tokens": output_tokens,
                "power": power,
                "power_id": power_id,
                "power_kind": power_kind,
                "run_id": run_id,
                "started_at": started_at,
                "status": status,
                "super_power": super_power,
                "super_power_id": super_power_id,
                "tool": tool,
                "user": user,
                "user_id": user_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cached_tokens = d.pop("cached_tokens")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        duration_ms = d.pop("duration_ms")

        def _parse_error_code(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        error_code = _parse_error_code(d.pop("error_code"))

        event_id = d.pop("event_id")

        id = UUID(d.pop("id"))

        input_tokens = d.pop("input_tokens")

        kind = d.pop("kind")

        def _parse_machine(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        machine = _parse_machine(d.pop("machine"))

        machine_id = UUID(d.pop("machine_id"))

        def _parse_model(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        model = _parse_model(d.pop("model"))

        output_tokens = d.pop("output_tokens")

        def _parse_power(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        power = _parse_power(d.pop("power"))

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

        def _parse_power_kind(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        power_kind = _parse_power_kind(d.pop("power_kind"))

        def _parse_run_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                run_id_type_0 = UUID(data)

                return run_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        run_id = _parse_run_id(d.pop("run_id"))

        started_at = datetime.datetime.fromisoformat(d.pop("started_at"))

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

        def _parse_tool(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        tool = _parse_tool(d.pop("tool"))

        def _parse_user(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        user = _parse_user(d.pop("user"))

        user_id = UUID(d.pop("user_id"))

        use = cls(
            cached_tokens=cached_tokens,
            created_at=created_at,
            duration_ms=duration_ms,
            error_code=error_code,
            event_id=event_id,
            id=id,
            input_tokens=input_tokens,
            kind=kind,
            machine=machine,
            machine_id=machine_id,
            model=model,
            output_tokens=output_tokens,
            power=power,
            power_id=power_id,
            power_kind=power_kind,
            run_id=run_id,
            started_at=started_at,
            status=status,
            super_power=super_power,
            super_power_id=super_power_id,
            tool=tool,
            user=user,
            user_id=user_id,
        )

        use.additional_properties = d
        return use

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
