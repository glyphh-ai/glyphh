from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.requirement import Requirement
    from ..models.review_view import ReviewView
    from ..models.shot import Shot


T = TypeVar("T", bound="VersionDetail")


@_attrs_define
class VersionDetail:
    """
    Attributes:
        id (UUID):
        needs (list[Requirement]):
        published_at (datetime.datetime | None):
        release_notes (str):
        reviews (list[ReviewView]):
        screenshots (list[Shot]):
        state (str):
        submitted_at (datetime.datetime | None):
        version (str):
    """

    id: UUID
    needs: list[Requirement]
    published_at: datetime.datetime | None
    release_notes: str
    reviews: list[ReviewView]
    screenshots: list[Shot]
    state: str
    submitted_at: datetime.datetime | None
    version: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        needs = []
        for needs_item_data in self.needs:
            needs_item = needs_item_data.to_dict()
            needs.append(needs_item)

        published_at: str | None
        if isinstance(self.published_at, datetime.datetime):
            published_at = self.published_at.isoformat()
        else:
            published_at = self.published_at

        release_notes = self.release_notes

        reviews = []
        for reviews_item_data in self.reviews:
            reviews_item = reviews_item_data.to_dict()
            reviews.append(reviews_item)

        screenshots = []
        for screenshots_item_data in self.screenshots:
            screenshots_item = screenshots_item_data.to_dict()
            screenshots.append(screenshots_item)

        state = self.state

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
                "id": id,
                "needs": needs,
                "published_at": published_at,
                "release_notes": release_notes,
                "reviews": reviews,
                "screenshots": screenshots,
                "state": state,
                "submitted_at": submitted_at,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.requirement import Requirement
        from ..models.review_view import ReviewView
        from ..models.shot import Shot

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        needs = []
        _needs = d.pop("needs")
        for needs_item_data in _needs:
            needs_item = Requirement.from_dict(needs_item_data)

            needs.append(needs_item)

        def _parse_published_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                published_at_type_0 = datetime.datetime.fromisoformat(data)

                return published_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        published_at = _parse_published_at(d.pop("published_at"))

        release_notes = d.pop("release_notes")

        reviews = []
        _reviews = d.pop("reviews")
        for reviews_item_data in _reviews:
            reviews_item = ReviewView.from_dict(reviews_item_data)

            reviews.append(reviews_item)

        screenshots = []
        _screenshots = d.pop("screenshots")
        for screenshots_item_data in _screenshots:
            screenshots_item = Shot.from_dict(screenshots_item_data)

            screenshots.append(screenshots_item)

        state = d.pop("state")

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

        version_detail = cls(
            id=id,
            needs=needs,
            published_at=published_at,
            release_notes=release_notes,
            reviews=reviews,
            screenshots=screenshots,
            state=state,
            submitted_at=submitted_at,
            version=version,
        )

        version_detail.additional_properties = d
        return version_detail

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
