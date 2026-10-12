from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.entry import Entry


T = TypeVar("T", bound="LimitView")


@_attrs_define
class LimitView:
    """
    Attributes:
        entries (list[Entry]):
        kind (str):
        left_out_people (int):
        limited (bool):
        org_limited (bool):
        team (None | str):
        total (int):
    """

    entries: list[Entry]
    kind: str
    left_out_people: int
    limited: bool
    org_limited: bool
    team: str | None
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        entries = []
        for entries_item_data in self.entries:
            entries_item = entries_item_data.to_dict()
            entries.append(entries_item)

        kind = self.kind

        left_out_people = self.left_out_people

        limited = self.limited

        org_limited = self.org_limited

        team: str | None
        team = self.team

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "entries": entries,
                "kind": kind,
                "left_out_people": left_out_people,
                "limited": limited,
                "org_limited": org_limited,
                "team": team,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.entry import Entry

        d = dict(src_dict)
        entries = []
        _entries = d.pop("entries")
        for entries_item_data in _entries:
            entries_item = Entry.from_dict(entries_item_data)

            entries.append(entries_item)

        kind = d.pop("kind")

        left_out_people = d.pop("left_out_people")

        limited = d.pop("limited")

        org_limited = d.pop("org_limited")

        def _parse_team(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        team = _parse_team(d.pop("team"))

        total = d.pop("total")

        limit_view = cls(
            entries=entries,
            kind=kind,
            left_out_people=left_out_people,
            limited=limited,
            org_limited=org_limited,
            team=team,
            total=total,
        )

        limit_view.additional_properties = d
        return limit_view

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
