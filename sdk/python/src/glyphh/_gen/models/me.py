from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.me_org import MeOrg


T = TypeVar("T", bound="Me")


@_attrs_define
class Me:
    """
    Attributes:
        email (str):
        first_name (None | str):
        id (UUID):
        image_url (None | str):
        last_name (None | str):
        org (MeOrg):
        role (str):
    """

    email: str
    first_name: str | None
    id: UUID
    image_url: str | None
    last_name: str | None
    org: MeOrg
    role: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        first_name: str | None
        first_name = self.first_name

        id = str(self.id)

        image_url: str | None
        image_url = self.image_url

        last_name: str | None
        last_name = self.last_name

        org = self.org.to_dict()

        role = self.role

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "first_name": first_name,
                "id": id,
                "image_url": image_url,
                "last_name": last_name,
                "org": org,
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.me_org import MeOrg

        d = dict(src_dict)
        email = d.pop("email")

        def _parse_first_name(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        first_name = _parse_first_name(d.pop("first_name"))

        id = UUID(d.pop("id"))

        def _parse_image_url(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        image_url = _parse_image_url(d.pop("image_url"))

        def _parse_last_name(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        last_name = _parse_last_name(d.pop("last_name"))

        org = MeOrg.from_dict(d.pop("org"))

        role = d.pop("role")

        me = cls(
            email=email,
            first_name=first_name,
            id=id,
            image_url=image_url,
            last_name=last_name,
            org=org,
            role=role,
        )

        me.additional_properties = d
        return me

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
