from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.counts import Counts
    from ..models.group import Group


T = TypeVar("T", bound="GroupPage")


@_attrs_define
class GroupPage:
    """
    Attributes:
        by (str):
        groups (list[Group]):
        sums (Counts):
        total (int):
    """

    by: str
    groups: list[Group]
    sums: Counts
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        by = self.by

        groups = []
        for groups_item_data in self.groups:
            groups_item = groups_item_data.to_dict()
            groups.append(groups_item)

        sums = self.sums.to_dict()

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "by": by,
                "groups": groups,
                "sums": sums,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.counts import Counts
        from ..models.group import Group

        d = dict(src_dict)
        by = d.pop("by")

        groups = []
        _groups = d.pop("groups")
        for groups_item_data in _groups:
            groups_item = Group.from_dict(groups_item_data)

            groups.append(groups_item)

        sums = Counts.from_dict(d.pop("sums"))

        total = d.pop("total")

        group_page = cls(
            by=by,
            groups=groups,
            sums=sums,
            total=total,
        )

        group_page.additional_properties = d
        return group_page

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
