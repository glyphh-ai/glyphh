from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ThreadChange")


@_attrs_define
class ThreadChange:
    """
    Attributes:
        archived (bool | None | Unset):
        goal (None | str | Unset):
        pinned (bool | None | Unset):
    """

    archived: bool | Unset | None = UNSET
    goal: str | Unset | None = UNSET
    pinned: bool | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        archived: bool | Unset | None
        if isinstance(self.archived, Unset):
            archived = UNSET
        else:
            archived = self.archived

        goal: str | Unset | None
        if isinstance(self.goal, Unset):
            goal = UNSET
        else:
            goal = self.goal

        pinned: bool | Unset | None
        if isinstance(self.pinned, Unset):
            pinned = UNSET
        else:
            pinned = self.pinned

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if archived is not UNSET:
            field_dict["archived"] = archived
        if goal is not UNSET:
            field_dict["goal"] = goal
        if pinned is not UNSET:
            field_dict["pinned"] = pinned

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_archived(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        archived = _parse_archived(d.pop("archived", UNSET))

        def _parse_goal(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        goal = _parse_goal(d.pop("goal", UNSET))

        def _parse_pinned(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        pinned = _parse_pinned(d.pop("pinned", UNSET))

        thread_change = cls(
            archived=archived,
            goal=goal,
            pinned=pinned,
        )

        thread_change.additional_properties = d
        return thread_change

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
