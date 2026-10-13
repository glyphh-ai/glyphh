from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.screen_call_ice_item import ScreenCallIceItem


T = TypeVar("T", bound="ScreenCall")


@_attrs_define
class ScreenCall:
    """
    Attributes:
        answer (str):
        call (UUID):
        ice (list[ScreenCallIceItem]):
    """

    answer: str
    call: UUID
    ice: list[ScreenCallIceItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        answer = self.answer

        call = str(self.call)

        ice = []
        for ice_item_data in self.ice:
            ice_item = ice_item_data.to_dict()
            ice.append(ice_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "answer": answer,
                "call": call,
                "ice": ice,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.screen_call_ice_item import ScreenCallIceItem

        d = dict(src_dict)
        answer = d.pop("answer")

        call = UUID(d.pop("call"))

        ice = []
        _ice = d.pop("ice")
        for ice_item_data in _ice:
            ice_item = ScreenCallIceItem.from_dict(ice_item_data)

            ice.append(ice_item)

        screen_call = cls(
            answer=answer,
            call=call,
            ice=ice,
        )

        screen_call.additional_properties = d
        return screen_call

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
