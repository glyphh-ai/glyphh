from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.crew_face import CrewFace


T = TypeVar("T", bound="Question")


@_attrs_define
class Question:
    """
    Attributes:
        asked_at (datetime.datetime):
        detail (str):
        id (UUID):
        kind (str):
        machine_id (UUID):
        machine_name (str):
        super_power (CrewFace | None):
        thread_goal (str):
        thread_id (UUID):
        tool (str):
    """

    asked_at: datetime.datetime
    detail: str
    id: UUID
    kind: str
    machine_id: UUID
    machine_name: str
    super_power: CrewFace | None
    thread_goal: str
    thread_id: UUID
    tool: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.crew_face import CrewFace

        asked_at = self.asked_at.isoformat()

        detail = self.detail

        id = str(self.id)

        kind = self.kind

        machine_id = str(self.machine_id)

        machine_name = self.machine_name

        super_power: dict[str, Any] | None
        if isinstance(self.super_power, CrewFace):
            super_power = self.super_power.to_dict()
        else:
            super_power = self.super_power

        thread_goal = self.thread_goal

        thread_id = str(self.thread_id)

        tool = self.tool

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "asked_at": asked_at,
                "detail": detail,
                "id": id,
                "kind": kind,
                "machine_id": machine_id,
                "machine_name": machine_name,
                "super_power": super_power,
                "thread_goal": thread_goal,
                "thread_id": thread_id,
                "tool": tool,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.crew_face import CrewFace

        d = dict(src_dict)
        asked_at = datetime.datetime.fromisoformat(d.pop("asked_at"))

        detail = d.pop("detail")

        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        machine_id = UUID(d.pop("machine_id"))

        machine_name = d.pop("machine_name")

        def _parse_super_power(data: object) -> CrewFace | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                super_power_type_0 = CrewFace.from_dict(data)

                return super_power_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CrewFace | None, data)

        super_power = _parse_super_power(d.pop("super_power"))

        thread_goal = d.pop("thread_goal")

        thread_id = UUID(d.pop("thread_id"))

        tool = d.pop("tool")

        question = cls(
            asked_at=asked_at,
            detail=detail,
            id=id,
            kind=kind,
            machine_id=machine_id,
            machine_name=machine_name,
            super_power=super_power,
            thread_goal=thread_goal,
            thread_id=thread_id,
            tool=tool,
        )

        question.additional_properties = d
        return question

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
