from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.by_version import ByVersion
    from ..models.run_day import RunDay


T = TypeVar("T", bound="ListingStats")


@_attrs_define
class ListingStats:
    """
    Attributes:
        days (list[RunDay]):
        failed_runs (int):
        installs (int):
        runs (int):
        since (datetime.date):
        used (int):
        versions (list[ByVersion]):
    """

    days: list[RunDay]
    failed_runs: int
    installs: int
    runs: int
    since: datetime.date
    used: int
    versions: list[ByVersion]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        days = []
        for days_item_data in self.days:
            days_item = days_item_data.to_dict()
            days.append(days_item)

        failed_runs = self.failed_runs

        installs = self.installs

        runs = self.runs

        since = self.since.isoformat()

        used = self.used

        versions = []
        for versions_item_data in self.versions:
            versions_item = versions_item_data.to_dict()
            versions.append(versions_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "days": days,
                "failed_runs": failed_runs,
                "installs": installs,
                "runs": runs,
                "since": since,
                "used": used,
                "versions": versions,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.by_version import ByVersion
        from ..models.run_day import RunDay

        d = dict(src_dict)
        days = []
        _days = d.pop("days")
        for days_item_data in _days:
            days_item = RunDay.from_dict(days_item_data)

            days.append(days_item)

        failed_runs = d.pop("failed_runs")

        installs = d.pop("installs")

        runs = d.pop("runs")

        since = datetime.date.fromisoformat(d.pop("since"))

        used = d.pop("used")

        versions = []
        _versions = d.pop("versions")
        for versions_item_data in _versions:
            versions_item = ByVersion.from_dict(versions_item_data)

            versions.append(versions_item)

        listing_stats = cls(
            days=days,
            failed_runs=failed_runs,
            installs=installs,
            runs=runs,
            since=since,
            used=used,
            versions=versions,
        )

        listing_stats.additional_properties = d
        return listing_stats

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
