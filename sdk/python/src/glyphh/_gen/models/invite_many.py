from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.invite_many_role import InviteManyRole
from ..types import UNSET, Unset

T = TypeVar("T", bound="InviteMany")


@_attrs_define
class InviteMany:
    """
    Attributes:
        emails (list[str]):
        role (InviteManyRole | Unset):  Default: InviteManyRole.USER.
        team_ids (list[UUID] | Unset):
    """

    emails: list[str]
    role: InviteManyRole | Unset = InviteManyRole.USER
    team_ids: list[UUID] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        emails = self.emails

        role: str | Unset = UNSET
        if not isinstance(self.role, Unset):
            role = self.role.value

        team_ids: list[str] | Unset = UNSET
        if not isinstance(self.team_ids, Unset):
            team_ids = []
            for team_ids_item_data in self.team_ids:
                team_ids_item = str(team_ids_item_data)
                team_ids.append(team_ids_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "emails": emails,
            }
        )
        if role is not UNSET:
            field_dict["role"] = role
        if team_ids is not UNSET:
            field_dict["team_ids"] = team_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        emails = cast(list[str], d.pop("emails"))

        _role = d.pop("role", UNSET)
        role: InviteManyRole | Unset
        if isinstance(_role, Unset):
            role = UNSET
        else:
            role = InviteManyRole(_role)

        _team_ids = d.pop("team_ids", UNSET)
        team_ids: list[UUID] | Unset = UNSET
        if _team_ids is not UNSET:
            team_ids = []
            for team_ids_item_data in _team_ids:
                team_ids_item = UUID(team_ids_item_data)

                team_ids.append(team_ids_item)

        invite_many = cls(
            emails=emails,
            role=role,
            team_ids=team_ids,
        )

        invite_many.additional_properties = d
        return invite_many

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
