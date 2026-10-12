from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.question import Question
    from ..models.thread_machine import ThreadMachine
    from ..models.thread_row import ThreadRow


T = TypeVar("T", bound="ThreadDetail")


@_attrs_define
class ThreadDetail:
    """
    Attributes:
        machine (ThreadMachine):
        questions (list[Question]):
        thread (ThreadRow):
    """

    machine: ThreadMachine
    questions: list[Question]
    thread: ThreadRow
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        machine = self.machine.to_dict()

        questions = []
        for questions_item_data in self.questions:
            questions_item = questions_item_data.to_dict()
            questions.append(questions_item)

        thread = self.thread.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "machine": machine,
                "questions": questions,
                "thread": thread,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.question import Question
        from ..models.thread_machine import ThreadMachine
        from ..models.thread_row import ThreadRow

        d = dict(src_dict)
        machine = ThreadMachine.from_dict(d.pop("machine"))

        questions = []
        _questions = d.pop("questions")
        for questions_item_data in _questions:
            questions_item = Question.from_dict(questions_item_data)

            questions.append(questions_item)

        thread = ThreadRow.from_dict(d.pop("thread"))

        thread_detail = cls(
            machine=machine,
            questions=questions,
            thread=thread,
        )

        thread_detail.additional_properties = d
        return thread_detail

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
