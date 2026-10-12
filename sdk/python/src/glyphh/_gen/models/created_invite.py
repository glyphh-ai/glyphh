from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.invite_view import InviteView


T = TypeVar("T", bound="CreatedInvite")


@_attrs_define
class CreatedInvite:
    """
    Attributes:
        invite (InviteView):
        link (str): The link to send the person: shown once, never stored
    """

    invite: InviteView
    link: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        invite = self.invite.to_dict()

        link = self.link

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "invite": invite,
                "link": link,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.invite_view import InviteView

        d = dict(src_dict)
        invite = InviteView.from_dict(d.pop("invite"))

        link = d.pop("link")

        created_invite = cls(
            invite=invite,
            link=link,
        )

        created_invite.additional_properties = d
        return created_invite

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
