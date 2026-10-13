from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.hosted_view_state import HostedViewState

T = TypeVar("T", bound="HostedView")


@_attrs_define
class HostedView:
    """
    Attributes:
        app (str):
        created_at (datetime.datetime):
        host (str):
        host_state (str):
        id (UUID):
        image (str):
        machine_id (None | UUID):
        name (str):
        region (str):
        state (HostedViewState):
    """

    app: str
    created_at: datetime.datetime
    host: str
    host_state: str
    id: UUID
    image: str
    machine_id: UUID | None
    name: str
    region: str
    state: HostedViewState
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        app = self.app

        created_at = self.created_at.isoformat()

        host = self.host

        host_state = self.host_state

        id = str(self.id)

        image = self.image

        machine_id: str | None
        if isinstance(self.machine_id, UUID):
            machine_id = str(self.machine_id)
        else:
            machine_id = self.machine_id

        name = self.name

        region = self.region

        state = self.state.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "app": app,
                "created_at": created_at,
                "host": host,
                "host_state": host_state,
                "id": id,
                "image": image,
                "machine_id": machine_id,
                "name": name,
                "region": region,
                "state": state,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        app = d.pop("app")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        host = d.pop("host")

        host_state = d.pop("host_state")

        id = UUID(d.pop("id"))

        image = d.pop("image")

        def _parse_machine_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                machine_id_type_0 = UUID(data)

                return machine_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        machine_id = _parse_machine_id(d.pop("machine_id"))

        name = d.pop("name")

        region = d.pop("region")

        state = HostedViewState(d.pop("state"))

        hosted_view = cls(
            app=app,
            created_at=created_at,
            host=host,
            host_state=host_state,
            id=id,
            image=image,
            machine_id=machine_id,
            name=name,
            region=region,
            state=state,
        )

        hosted_view.additional_properties = d
        return hosted_view

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
