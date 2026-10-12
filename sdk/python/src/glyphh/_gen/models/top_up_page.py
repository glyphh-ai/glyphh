from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.top_up import TopUp


T = TypeVar("T", bound="TopUpPage")


@_attrs_define
class TopUpPage:
    """
    Attributes:
        top_ups (list[TopUp]):
        total (int):
    """

    top_ups: list[TopUp]
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        top_ups = []
        for top_ups_item_data in self.top_ups:
            top_ups_item = top_ups_item_data.to_dict()
            top_ups.append(top_ups_item)

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "top_ups": top_ups,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.top_up import TopUp

        d = dict(src_dict)
        top_ups = []
        _top_ups = d.pop("top_ups")
        for top_ups_item_data in _top_ups:
            top_ups_item = TopUp.from_dict(top_ups_item_data)

            top_ups.append(top_ups_item)

        total = d.pop("total")

        top_up_page = cls(
            top_ups=top_ups,
            total=total,
        )

        top_up_page.additional_properties = d
        return top_up_page

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
