from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="RunUse")


@_attrs_define
class RunUse:
    """
    Attributes:
        cost_cents (int):
        ended_at (datetime.datetime):
        errors (int):
        machine (None | str):
        machine_id (None | UUID):
        run_id (UUID):
        started_at (datetime.datetime):
        uses (int):
    """

    cost_cents: int
    ended_at: datetime.datetime
    errors: int
    machine: str | None
    machine_id: UUID | None
    run_id: UUID
    started_at: datetime.datetime
    uses: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cost_cents = self.cost_cents

        ended_at = self.ended_at.isoformat()

        errors = self.errors

        machine: str | None
        machine = self.machine

        machine_id: str | None
        if isinstance(self.machine_id, UUID):
            machine_id = str(self.machine_id)
        else:
            machine_id = self.machine_id

        run_id = str(self.run_id)

        started_at = self.started_at.isoformat()

        uses = self.uses

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cost_cents": cost_cents,
                "ended_at": ended_at,
                "errors": errors,
                "machine": machine,
                "machine_id": machine_id,
                "run_id": run_id,
                "started_at": started_at,
                "uses": uses,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cost_cents = d.pop("cost_cents")

        ended_at = datetime.datetime.fromisoformat(d.pop("ended_at"))

        errors = d.pop("errors")

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

        run_id = UUID(d.pop("run_id"))

        started_at = datetime.datetime.fromisoformat(d.pop("started_at"))

        uses = d.pop("uses")

        run_use = cls(
            cost_cents=cost_cents,
            ended_at=ended_at,
            errors=errors,
            machine=machine,
            machine_id=machine_id,
            run_id=run_id,
            started_at=started_at,
            uses=uses,
        )

        run_use.additional_properties = d
        return run_use

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
