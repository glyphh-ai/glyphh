from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="InReview")


@_attrs_define
class InReview:
    """
    Attributes:
        by (str):
        kind (str):
        listing_id (UUID):
        listing_version_id (UUID):
        name (str):
        reach (str):
        submitted_at (datetime.datetime | None):
        version (str):
    """

    by: str
    kind: str
    listing_id: UUID
    listing_version_id: UUID
    name: str
    reach: str
    submitted_at: datetime.datetime | None
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        by = self.by

        kind = self.kind

        listing_id = str(self.listing_id)

        listing_version_id = str(self.listing_version_id)

        name = self.name

        reach = self.reach

        submitted_at: str | None
        if isinstance(self.submitted_at, datetime.datetime):
            submitted_at = self.submitted_at.isoformat()
        else:
            submitted_at = self.submitted_at

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "by": by,
                "kind": kind,
                "listing_id": listing_id,
                "listing_version_id": listing_version_id,
                "name": name,
                "reach": reach,
                "submitted_at": submitted_at,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        by = d.pop("by")

        kind = d.pop("kind")

        listing_id = UUID(d.pop("listing_id"))

        listing_version_id = UUID(d.pop("listing_version_id"))

        name = d.pop("name")

        reach = d.pop("reach")

        def _parse_submitted_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                submitted_at_type_0 = datetime.datetime.fromisoformat(data)

                return submitted_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        submitted_at = _parse_submitted_at(d.pop("submitted_at"))

        version = d.pop("version")

        in_review = cls(
            by=by,
            kind=kind,
            listing_id=listing_id,
            listing_version_id=listing_version_id,
            name=name,
            reach=reach,
            submitted_at=submitted_at,
            version=version,
        )

        in_review.additional_properties = d
        return in_review

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
