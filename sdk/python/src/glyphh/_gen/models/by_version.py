from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ByVersion")


@_attrs_define
class ByVersion:
    """
    Attributes:
        installs (int):
        live (bool):
        runs (int):
        version (str):
    """

    installs: int
    live: bool
    runs: int
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        installs = self.installs

        live = self.live

        runs = self.runs

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "installs": installs,
                "live": live,
                "runs": runs,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        installs = d.pop("installs")

        live = d.pop("live")

        runs = d.pop("runs")

        version = d.pop("version")

        by_version = cls(
            installs=installs,
            live=live,
            runs=runs,
            version=version,
        )

        by_version.additional_properties = d
        return by_version

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
