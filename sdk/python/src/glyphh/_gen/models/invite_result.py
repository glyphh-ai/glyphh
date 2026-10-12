from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.refused import Refused
    from ..models.sent import Sent


T = TypeVar("T", bound="InviteResult")


@_attrs_define
class InviteResult:
    """
    Attributes:
        refused (list[Refused]):
        sent (list[Sent]):
    """

    refused: list[Refused]
    sent: list[Sent]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        refused = []
        for refused_item_data in self.refused:
            refused_item = refused_item_data.to_dict()
            refused.append(refused_item)

        sent = []
        for sent_item_data in self.sent:
            sent_item = sent_item_data.to_dict()
            sent.append(sent_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "refused": refused,
                "sent": sent,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.refused import Refused
        from ..models.sent import Sent

        d = dict(src_dict)
        refused = []
        _refused = d.pop("refused")
        for refused_item_data in _refused:
            refused_item = Refused.from_dict(refused_item_data)

            refused.append(refused_item)

        sent = []
        _sent = d.pop("sent")
        for sent_item_data in _sent:
            sent_item = Sent.from_dict(sent_item_data)

            sent.append(sent_item)

        invite_result = cls(
            refused=refused,
            sent=sent,
        )

        invite_result.additional_properties = d
        return invite_result

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
