from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.crew_face import CrewFace


T = TypeVar("T", bound="ThreadRow")


@_attrs_define
class ThreadRow:
    """
    Attributes:
        archived_at (datetime.datetime | None):
        created_at (datetime.datetime):
        crew (list[CrewFace]):
        goal (str):
        id (UUID):
        last_event_at (datetime.datetime):
        last_seq (int):
        machine_id (UUID):
        needs_you (int):
        pinned_at (datetime.datetime | None):
        status (str):
        super_power (CrewFace | None):
    """

    archived_at: datetime.datetime | None
    created_at: datetime.datetime
    crew: list[CrewFace]
    goal: str
    id: UUID
    last_event_at: datetime.datetime
    last_seq: int
    machine_id: UUID
    needs_you: int
    pinned_at: datetime.datetime | None
    status: str
    super_power: CrewFace | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.crew_face import CrewFace

        archived_at: str | None
        if isinstance(self.archived_at, datetime.datetime):
            archived_at = self.archived_at.isoformat()
        else:
            archived_at = self.archived_at

        created_at = self.created_at.isoformat()

        crew = []
        for crew_item_data in self.crew:
            crew_item = crew_item_data.to_dict()
            crew.append(crew_item)

        goal = self.goal

        id = str(self.id)

        last_event_at = self.last_event_at.isoformat()

        last_seq = self.last_seq

        machine_id = str(self.machine_id)

        needs_you = self.needs_you

        pinned_at: str | None
        if isinstance(self.pinned_at, datetime.datetime):
            pinned_at = self.pinned_at.isoformat()
        else:
            pinned_at = self.pinned_at

        status = self.status

        super_power: dict[str, Any] | None
        if isinstance(self.super_power, CrewFace):
            super_power = self.super_power.to_dict()
        else:
            super_power = self.super_power

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "archived_at": archived_at,
                "created_at": created_at,
                "crew": crew,
                "goal": goal,
                "id": id,
                "last_event_at": last_event_at,
                "last_seq": last_seq,
                "machine_id": machine_id,
                "needs_you": needs_you,
                "pinned_at": pinned_at,
                "status": status,
                "super_power": super_power,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.crew_face import CrewFace

        d = dict(src_dict)

        def _parse_archived_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                archived_at_type_0 = datetime.datetime.fromisoformat(data)

                return archived_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        archived_at = _parse_archived_at(d.pop("archived_at"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        crew = []
        _crew = d.pop("crew")
        for crew_item_data in _crew:
            crew_item = CrewFace.from_dict(crew_item_data)

            crew.append(crew_item)

        goal = d.pop("goal")

        id = UUID(d.pop("id"))

        last_event_at = datetime.datetime.fromisoformat(d.pop("last_event_at"))

        last_seq = d.pop("last_seq")

        machine_id = UUID(d.pop("machine_id"))

        needs_you = d.pop("needs_you")

        def _parse_pinned_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                pinned_at_type_0 = datetime.datetime.fromisoformat(data)

                return pinned_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        pinned_at = _parse_pinned_at(d.pop("pinned_at"))

        status = d.pop("status")

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

        thread_row = cls(
            archived_at=archived_at,
            created_at=created_at,
            crew=crew,
            goal=goal,
            id=id,
            last_event_at=last_event_at,
            last_seq=last_seq,
            machine_id=machine_id,
            needs_you=needs_you,
            pinned_at=pinned_at,
            status=status,
            super_power=super_power,
        )

        thread_row.additional_properties = d
        return thread_row

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
