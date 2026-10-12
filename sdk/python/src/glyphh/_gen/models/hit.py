from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Hit")


@_attrs_define
class Hit:
    """
    Attributes:
        at (datetime.datetime):
        goal (str):
        machine_id (UUID):
        seq (int | None):
        snippet (None | str):
        thread_id (UUID):
    """

    at: datetime.datetime
    goal: str
    machine_id: UUID
    seq: int | None
    snippet: str | None
    thread_id: UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        at = self.at.isoformat()

        goal = self.goal

        machine_id = str(self.machine_id)

        seq: int | None
        seq = self.seq

        snippet: str | None
        snippet = self.snippet

        thread_id = str(self.thread_id)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "at": at,
                "goal": goal,
                "machine_id": machine_id,
                "seq": seq,
                "snippet": snippet,
                "thread_id": thread_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        at = datetime.datetime.fromisoformat(d.pop("at"))

        goal = d.pop("goal")

        machine_id = UUID(d.pop("machine_id"))

        def _parse_seq(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        seq = _parse_seq(d.pop("seq"))

        def _parse_snippet(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        snippet = _parse_snippet(d.pop("snippet"))

        thread_id = UUID(d.pop("thread_id"))

        hit = cls(
            at=at,
            goal=goal,
            machine_id=machine_id,
            seq=seq,
            snippet=snippet,
            thread_id=thread_id,
        )

        hit.additional_properties = d
        return hit

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
