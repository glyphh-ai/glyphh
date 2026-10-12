from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="Tiles")


@_attrs_define
class Tiles:
    """
    Attributes:
        members (int):
        people (int):
        refused (int):
        runs (int):
        cached_tokens (int | Unset):  Default: 0.
        connection_calls (int | Unset):  Default: 0.
        cost_cents (int | Unset):  Default: 0.
        duration_ms (int | Unset):  Default: 0.
        errors (int | Unset):  Default: 0.
        input_tokens (int | Unset):  Default: 0.
        output_tokens (int | Unset):  Default: 0.
        uses (int | Unset):  Default: 0.
    """

    members: int
    people: int
    refused: int
    runs: int
    cached_tokens: int | Unset = 0
    connection_calls: int | Unset = 0
    cost_cents: int | Unset = 0
    duration_ms: int | Unset = 0
    errors: int | Unset = 0
    input_tokens: int | Unset = 0
    output_tokens: int | Unset = 0
    uses: int | Unset = 0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        members = self.members

        people = self.people

        refused = self.refused

        runs = self.runs

        cached_tokens = self.cached_tokens

        connection_calls = self.connection_calls

        cost_cents = self.cost_cents

        duration_ms = self.duration_ms

        errors = self.errors

        input_tokens = self.input_tokens

        output_tokens = self.output_tokens

        uses = self.uses

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "members": members,
                "people": people,
                "refused": refused,
                "runs": runs,
            }
        )
        if cached_tokens is not UNSET:
            field_dict["cached_tokens"] = cached_tokens
        if connection_calls is not UNSET:
            field_dict["connection_calls"] = connection_calls
        if cost_cents is not UNSET:
            field_dict["cost_cents"] = cost_cents
        if duration_ms is not UNSET:
            field_dict["duration_ms"] = duration_ms
        if errors is not UNSET:
            field_dict["errors"] = errors
        if input_tokens is not UNSET:
            field_dict["input_tokens"] = input_tokens
        if output_tokens is not UNSET:
            field_dict["output_tokens"] = output_tokens
        if uses is not UNSET:
            field_dict["uses"] = uses

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        members = d.pop("members")

        people = d.pop("people")

        refused = d.pop("refused")

        runs = d.pop("runs")

        cached_tokens = d.pop("cached_tokens", UNSET)

        connection_calls = d.pop("connection_calls", UNSET)

        cost_cents = d.pop("cost_cents", UNSET)

        duration_ms = d.pop("duration_ms", UNSET)

        errors = d.pop("errors", UNSET)

        input_tokens = d.pop("input_tokens", UNSET)

        output_tokens = d.pop("output_tokens", UNSET)

        uses = d.pop("uses", UNSET)

        tiles = cls(
            members=members,
            people=people,
            refused=refused,
            runs=runs,
            cached_tokens=cached_tokens,
            connection_calls=connection_calls,
            cost_cents=cost_cents,
            duration_ms=duration_ms,
            errors=errors,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            uses=uses,
        )

        tiles.additional_properties = d
        return tiles

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
