from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.machine_says_host import MachineSaysHost
from ..models.machine_says_platform import MachineSaysPlatform

T = TypeVar("T", bound="MachineSays")


@_attrs_define
class MachineSays:
    """What a machine says it is when it signs in.

    Attributes:
        host (MachineSaysHost):
        name (str):
        platform (MachineSaysPlatform):
        ssh_public_key (str):
    """

    host: MachineSaysHost
    name: str
    platform: MachineSaysPlatform
    ssh_public_key: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        host = self.host.value

        name = self.name

        platform = self.platform.value

        ssh_public_key = self.ssh_public_key

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "host": host,
                "name": name,
                "platform": platform,
                "ssh_public_key": ssh_public_key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        host = MachineSaysHost(d.pop("host"))

        name = d.pop("name")

        platform = MachineSaysPlatform(d.pop("platform"))

        ssh_public_key = d.pop("ssh_public_key")

        machine_says = cls(
            host=host,
            name=name,
            platform=platform,
            ssh_public_key=ssh_public_key,
        )

        machine_says.additional_properties = d
        return machine_says

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
