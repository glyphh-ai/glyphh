from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.relayed_result import RelayedResult


T = TypeVar("T", bound="Relayed")


@_attrs_define
class Relayed:
    """
    Attributes:
        cost_cents (int):
        duration_ms (int):
        error (None | str):
        id (UUID):
        result (RelayedResult):
        status (str):
        trace_id (None | str):
    """

    cost_cents: int
    duration_ms: int
    error: str | None
    id: UUID
    result: RelayedResult
    status: str
    trace_id: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cost_cents = self.cost_cents

        duration_ms = self.duration_ms

        error: str | None
        error = self.error

        id = str(self.id)

        result = self.result.to_dict()

        status = self.status

        trace_id: str | None
        trace_id = self.trace_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cost_cents": cost_cents,
                "duration_ms": duration_ms,
                "error": error,
                "id": id,
                "result": result,
                "status": status,
                "trace_id": trace_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.relayed_result import RelayedResult

        d = dict(src_dict)
        cost_cents = d.pop("cost_cents")

        duration_ms = d.pop("duration_ms")

        def _parse_error(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        error = _parse_error(d.pop("error"))

        id = UUID(d.pop("id"))

        result = RelayedResult.from_dict(d.pop("result"))

        status = d.pop("status")

        def _parse_trace_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        trace_id = _parse_trace_id(d.pop("trace_id"))

        relayed = cls(
            cost_cents=cost_cents,
            duration_ms=duration_ms,
            error=error,
            id=id,
            result=result,
            status=status,
            trace_id=trace_id,
        )

        relayed.additional_properties = d
        return relayed

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
