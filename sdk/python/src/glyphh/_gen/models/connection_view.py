from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.connection_view_state import ConnectionViewState

if TYPE_CHECKING:
    from ..models.user import User


T = TypeVar("T", bound="ConnectionView")


@_attrs_define
class ConnectionView:
    """
    Attributes:
        account_label (None | str):
        allowed_tools (int):
        connected_at (datetime.datetime | None):
        denied_tools (int):
        disabled_reason (None | str):
        id (UUID):
        name (str):
        service (str):
        state (ConnectionViewState):
        used_by (list[User]):
    """

    account_label: str | None
    allowed_tools: int
    connected_at: datetime.datetime | None
    denied_tools: int
    disabled_reason: str | None
    id: UUID
    name: str
    service: str
    state: ConnectionViewState
    used_by: list[User]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account_label: str | None
        account_label = self.account_label

        allowed_tools = self.allowed_tools

        connected_at: str | None
        if isinstance(self.connected_at, datetime.datetime):
            connected_at = self.connected_at.isoformat()
        else:
            connected_at = self.connected_at

        denied_tools = self.denied_tools

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        id = str(self.id)

        name = self.name

        service = self.service

        state = self.state.value

        used_by = []
        for used_by_item_data in self.used_by:
            used_by_item = used_by_item_data.to_dict()
            used_by.append(used_by_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account_label": account_label,
                "allowed_tools": allowed_tools,
                "connected_at": connected_at,
                "denied_tools": denied_tools,
                "disabled_reason": disabled_reason,
                "id": id,
                "name": name,
                "service": service,
                "state": state,
                "used_by": used_by,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user import User

        d = dict(src_dict)

        def _parse_account_label(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        account_label = _parse_account_label(d.pop("account_label"))

        allowed_tools = d.pop("allowed_tools")

        def _parse_connected_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                connected_at_type_0 = datetime.datetime.fromisoformat(data)

                return connected_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        connected_at = _parse_connected_at(d.pop("connected_at"))

        denied_tools = d.pop("denied_tools")

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        id = UUID(d.pop("id"))

        name = d.pop("name")

        service = d.pop("service")

        state = ConnectionViewState(d.pop("state"))

        used_by = []
        _used_by = d.pop("used_by")
        for used_by_item_data in _used_by:
            used_by_item = User.from_dict(used_by_item_data)

            used_by.append(used_by_item)

        connection_view = cls(
            account_label=account_label,
            allowed_tools=allowed_tools,
            connected_at=connected_at,
            denied_tools=denied_tools,
            disabled_reason=disabled_reason,
            id=id,
            name=name,
            service=service,
            state=state,
            used_by=used_by,
        )

        connection_view.additional_properties = d
        return connection_view

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
