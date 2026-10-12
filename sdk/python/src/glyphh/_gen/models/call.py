from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Call")


@_attrs_define
class Call:
    """
    Attributes:
        account (None | str):
        cost_cents (int):
        created_at (datetime.datetime):
        duration_ms (int):
        error (None | str):
        id (UUID):
        machine (None | str):
        machine_id (None | UUID):
        power_id (None | UUID):
        request_bytes (int):
        response_bytes (int):
        run_id (None | UUID):
        service (str):
        started_at (datetime.datetime):
        status (str):
        super_power (None | str):
        super_power_id (None | UUID):
        tool (str):
        trace_id (None | str):
        user (None | str):
        user_id (UUID):
    """

    account: str | None
    cost_cents: int
    created_at: datetime.datetime
    duration_ms: int
    error: str | None
    id: UUID
    machine: str | None
    machine_id: UUID | None
    power_id: UUID | None
    request_bytes: int
    response_bytes: int
    run_id: UUID | None
    service: str
    started_at: datetime.datetime
    status: str
    super_power: str | None
    super_power_id: UUID | None
    tool: str
    trace_id: str | None
    user: str | None
    user_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account: str | None
        account = self.account

        cost_cents = self.cost_cents

        created_at = self.created_at.isoformat()

        duration_ms = self.duration_ms

        error: str | None
        error = self.error

        id = str(self.id)

        machine: str | None
        machine = self.machine

        machine_id: str | None
        if isinstance(self.machine_id, UUID):
            machine_id = str(self.machine_id)
        else:
            machine_id = self.machine_id

        power_id: str | None
        if isinstance(self.power_id, UUID):
            power_id = str(self.power_id)
        else:
            power_id = self.power_id

        request_bytes = self.request_bytes

        response_bytes = self.response_bytes

        run_id: str | None
        if isinstance(self.run_id, UUID):
            run_id = str(self.run_id)
        else:
            run_id = self.run_id

        service = self.service

        started_at = self.started_at.isoformat()

        status = self.status

        super_power: str | None
        super_power = self.super_power

        super_power_id: str | None
        if isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        tool = self.tool

        trace_id: str | None
        trace_id = self.trace_id

        user: str | None
        user = self.user

        user_id = str(self.user_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account": account,
                "cost_cents": cost_cents,
                "created_at": created_at,
                "duration_ms": duration_ms,
                "error": error,
                "id": id,
                "machine": machine,
                "machine_id": machine_id,
                "power_id": power_id,
                "request_bytes": request_bytes,
                "response_bytes": response_bytes,
                "run_id": run_id,
                "service": service,
                "started_at": started_at,
                "status": status,
                "super_power": super_power,
                "super_power_id": super_power_id,
                "tool": tool,
                "trace_id": trace_id,
                "user": user,
                "user_id": user_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_account(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        account = _parse_account(d.pop("account"))

        cost_cents = d.pop("cost_cents")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        duration_ms = d.pop("duration_ms")

        def _parse_error(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        error = _parse_error(d.pop("error"))

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

        request_bytes = d.pop("request_bytes")

        response_bytes = d.pop("response_bytes")

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

        service = d.pop("service")

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

        tool = d.pop("tool")

        def _parse_trace_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        trace_id = _parse_trace_id(d.pop("trace_id"))

        def _parse_user(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        user = _parse_user(d.pop("user"))

        user_id = UUID(d.pop("user_id"))

        call = cls(
            account=account,
            cost_cents=cost_cents,
            created_at=created_at,
            duration_ms=duration_ms,
            error=error,
            id=id,
            machine=machine,
            machine_id=machine_id,
            power_id=power_id,
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            run_id=run_id,
            service=service,
            started_at=started_at,
            status=status,
            super_power=super_power,
            super_power_id=super_power_id,
            tool=tool,
            trace_id=trace_id,
            user=user,
            user_id=user_id,
        )

        call.additional_properties = d
        return call

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
