from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.connection_view import ConnectionView


T = TypeVar("T", bound="ConnectLink")


@_attrs_define
class ConnectLink:
    """
    Attributes:
        connection (ConnectionView):
        expires_at (str):
        url (str):
    """

    connection: ConnectionView
    expires_at: str
    url: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        connection = self.connection.to_dict()

        expires_at = self.expires_at

        url = self.url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "connection": connection,
                "expires_at": expires_at,
                "url": url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connection_view import ConnectionView

        d = dict(src_dict)
        connection = ConnectionView.from_dict(d.pop("connection"))

        expires_at = d.pop("expires_at")

        url = d.pop("url")

        connect_link = cls(
            connection=connection,
            expires_at=expires_at,
            url=url,
        )

        connect_link.additional_properties = d
        return connect_link

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
