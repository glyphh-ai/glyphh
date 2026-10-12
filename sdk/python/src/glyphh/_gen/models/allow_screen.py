from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.me_org import MeOrg


T = TypeVar("T", bound="AllowScreen")


@_attrs_define
class AllowScreen:
    """
    Attributes:
        email (str):
        host (str):
        orgs (list[MeOrg]):
    """

    email: str
    host: str
    orgs: list[MeOrg]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        host = self.host

        orgs = []
        for orgs_item_data in self.orgs:
            orgs_item = orgs_item_data.to_dict()
            orgs.append(orgs_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "host": host,
                "orgs": orgs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.me_org import MeOrg

        d = dict(src_dict)
        email = d.pop("email")

        host = d.pop("host")

        orgs = []
        _orgs = d.pop("orgs")
        for orgs_item_data in _orgs:
            orgs_item = MeOrg.from_dict(orgs_item_data)

            orgs.append(orgs_item)

        allow_screen = cls(
            email=email,
            host=host,
            orgs=orgs,
        )

        allow_screen.additional_properties = d
        return allow_screen

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
