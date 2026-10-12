from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.custom_power_flow_type_0 import CustomPowerFlowType0
    from ..models.file import File
    from ..models.needed import Needed
    from ..models.part import Part
    from ..models.user import User


T = TypeVar("T", bound="CustomPower")


@_attrs_define
class CustomPower:
    """
    Attributes:
        connections (list[Needed]):
        description (str):
        disabled_reason (None | str):
        files (list[File]):
        flow (CustomPowerFlowType0 | None):
        id (UUID):
        installed (bool):
        kind (str):
        name (str):
        parts (list[Part]):
        updated_at (datetime.datetime):
        used_by (list[User]):
    """

    connections: list[Needed]
    description: str
    disabled_reason: str | None
    files: list[File]
    flow: CustomPowerFlowType0 | None
    id: UUID
    installed: bool
    kind: str
    name: str
    parts: list[Part]
    updated_at: datetime.datetime
    used_by: list[User]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.custom_power_flow_type_0 import CustomPowerFlowType0

        connections = []
        for connections_item_data in self.connections:
            connections_item = connections_item_data.to_dict()
            connections.append(connections_item)

        description = self.description

        disabled_reason: str | None
        disabled_reason = self.disabled_reason

        files = []
        for files_item_data in self.files:
            files_item = files_item_data.to_dict()
            files.append(files_item)

        flow: dict[str, Any] | None
        if isinstance(self.flow, CustomPowerFlowType0):
            flow = self.flow.to_dict()
        else:
            flow = self.flow

        id = str(self.id)

        installed = self.installed

        kind = self.kind

        name = self.name

        parts = []
        for parts_item_data in self.parts:
            parts_item = parts_item_data.to_dict()
            parts.append(parts_item)

        updated_at = self.updated_at.isoformat()

        used_by = []
        for used_by_item_data in self.used_by:
            used_by_item = used_by_item_data.to_dict()
            used_by.append(used_by_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "connections": connections,
                "description": description,
                "disabled_reason": disabled_reason,
                "files": files,
                "flow": flow,
                "id": id,
                "installed": installed,
                "kind": kind,
                "name": name,
                "parts": parts,
                "updated_at": updated_at,
                "used_by": used_by,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.custom_power_flow_type_0 import CustomPowerFlowType0
        from ..models.file import File
        from ..models.needed import Needed
        from ..models.part import Part
        from ..models.user import User

        d = dict(src_dict)
        connections = []
        _connections = d.pop("connections")
        for connections_item_data in _connections:
            connections_item = Needed.from_dict(connections_item_data)

            connections.append(connections_item)

        description = d.pop("description")

        def _parse_disabled_reason(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        files = []
        _files = d.pop("files")
        for files_item_data in _files:
            files_item = File.from_dict(files_item_data)

            files.append(files_item)

        def _parse_flow(data: object) -> CustomPowerFlowType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                flow_type_0 = CustomPowerFlowType0.from_dict(data)

                return flow_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CustomPowerFlowType0 | None, data)

        flow = _parse_flow(d.pop("flow"))

        id = UUID(d.pop("id"))

        installed = d.pop("installed")

        kind = d.pop("kind")

        name = d.pop("name")

        parts = []
        _parts = d.pop("parts")
        for parts_item_data in _parts:
            parts_item = Part.from_dict(parts_item_data)

            parts.append(parts_item)

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        used_by = []
        _used_by = d.pop("used_by")
        for used_by_item_data in _used_by:
            used_by_item = User.from_dict(used_by_item_data)

            used_by.append(used_by_item)

        custom_power = cls(
            connections=connections,
            description=description,
            disabled_reason=disabled_reason,
            files=files,
            flow=flow,
            id=id,
            installed=installed,
            kind=kind,
            name=name,
            parts=parts,
            updated_at=updated_at,
            used_by=used_by,
        )

        custom_power.additional_properties = d
        return custom_power

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
