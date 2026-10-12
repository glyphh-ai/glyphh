from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.crew_count import CrewCount
    from ..models.thread_row import ThreadRow


T = TypeVar("T", bound="ThreadPage")


@_attrs_define
class ThreadPage:
    """
    Attributes:
        crew (list[CrewCount]):
        machine (str):
        threads (list[ThreadRow]):
        total (int):
    """

    crew: list[CrewCount]
    machine: str
    threads: list[ThreadRow]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        crew = []
        for crew_item_data in self.crew:
            crew_item = crew_item_data.to_dict()
            crew.append(crew_item)

        machine = self.machine

        threads = []
        for threads_item_data in self.threads:
            threads_item = threads_item_data.to_dict()
            threads.append(threads_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "crew": crew,
                "machine": machine,
                "threads": threads,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.crew_count import CrewCount
        from ..models.thread_row import ThreadRow

        d = dict(src_dict)
        crew = []
        _crew = d.pop("crew")
        for crew_item_data in _crew:
            crew_item = CrewCount.from_dict(crew_item_data)

            crew.append(crew_item)

        machine = d.pop("machine")

        threads = []
        _threads = d.pop("threads")
        for threads_item_data in _threads:
            threads_item = ThreadRow.from_dict(threads_item_data)

            threads.append(threads_item)

        total = d.pop("total")

        thread_page = cls(
            crew=crew,
            machine=machine,
            threads=threads,
            total=total,
        )

        thread_page.additional_properties = d
        return thread_page

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
