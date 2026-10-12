from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.use import Use


T = TypeVar("T", bound="UsePage")


@_attrs_define
class UsePage:
    """
    Attributes:
        next_ (None | str):
        total (int):
        uses (list[Use]):
    """

    next_: str | None
    total: int
    uses: list[Use]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        next_: str | None
        next_ = self.next_

        total = self.total

        uses = []
        for uses_item_data in self.uses:
            uses_item = uses_item_data.to_dict()
            uses.append(uses_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "next": next_,
                "total": total,
                "uses": uses,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.use import Use

        d = dict(src_dict)

        def _parse_next_(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        next_ = _parse_next_(d.pop("next"))

        total = d.pop("total")

        uses = []
        _uses = d.pop("uses")
        for uses_item_data in _uses:
            uses_item = Use.from_dict(uses_item_data)

            uses.append(uses_item)

        use_page = cls(
            next_=next_,
            total=total,
            uses=uses,
        )

        use_page.additional_properties = d
        return use_page

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
