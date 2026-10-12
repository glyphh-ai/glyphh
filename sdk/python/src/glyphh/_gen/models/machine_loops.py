from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.loop_state import LoopState


T = TypeVar("T", bound="MachineLoops")


@_attrs_define
class MachineLoops:
    """
    Attributes:
        last_seen_at (datetime.datetime | None):
        loops (list[LoopState]):
        machine (str):
        machine_id (UUID):
        online (bool):
    """

    last_seen_at: datetime.datetime | None
    loops: list[LoopState]
    machine: str
    machine_id: UUID
    online: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        last_seen_at: str | None
        if isinstance(self.last_seen_at, datetime.datetime):
            last_seen_at = self.last_seen_at.isoformat()
        else:
            last_seen_at = self.last_seen_at

        loops = []
        for loops_item_data in self.loops:
            loops_item = loops_item_data.to_dict()
            loops.append(loops_item)

        machine = self.machine

        machine_id = str(self.machine_id)

        online = self.online

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "last_seen_at": last_seen_at,
                "loops": loops,
                "machine": machine,
                "machine_id": machine_id,
                "online": online,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.loop_state import LoopState

        d = dict(src_dict)

        def _parse_last_seen_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_seen_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_seen_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_seen_at = _parse_last_seen_at(d.pop("last_seen_at"))

        loops = []
        _loops = d.pop("loops")
        for loops_item_data in _loops:
            loops_item = LoopState.from_dict(loops_item_data)

            loops.append(loops_item)

        machine = d.pop("machine")

        machine_id = UUID(d.pop("machine_id"))

        online = d.pop("online")

        machine_loops = cls(
            last_seen_at=last_seen_at,
            loops=loops,
            machine=machine,
            machine_id=machine_id,
            online=online,
        )

        machine_loops.additional_properties = d
        return machine_loops

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
