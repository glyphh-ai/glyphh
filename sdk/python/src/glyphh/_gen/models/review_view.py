from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.review_view_agent_report_type_0 import ReviewViewAgentReportType0


T = TypeVar("T", bound="ReviewView")


@_attrs_define
class ReviewView:
    """
    Attributes:
        agent_report (None | ReviewViewAgentReportType0):
        decided_at (datetime.datetime | None):
        decision (None | str):
        notes (None | str):
        reviewer (None | str):
        step (str):
    """

    agent_report: ReviewViewAgentReportType0 | None
    decided_at: datetime.datetime | None
    decision: str | None
    notes: str | None
    reviewer: str | None
    step: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.review_view_agent_report_type_0 import ReviewViewAgentReportType0

        agent_report: dict[str, Any] | None
        if isinstance(self.agent_report, ReviewViewAgentReportType0):
            agent_report = self.agent_report.to_dict()
        else:
            agent_report = self.agent_report

        decided_at: str | None
        if isinstance(self.decided_at, datetime.datetime):
            decided_at = self.decided_at.isoformat()
        else:
            decided_at = self.decided_at

        decision: str | None
        decision = self.decision

        notes: str | None
        notes = self.notes

        reviewer: str | None
        reviewer = self.reviewer

        step = self.step

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "agent_report": agent_report,
                "decided_at": decided_at,
                "decision": decision,
                "notes": notes,
                "reviewer": reviewer,
                "step": step,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.review_view_agent_report_type_0 import ReviewViewAgentReportType0

        d = dict(src_dict)

        def _parse_agent_report(data: object) -> ReviewViewAgentReportType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                agent_report_type_0 = ReviewViewAgentReportType0.from_dict(data)

                return agent_report_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ReviewViewAgentReportType0, data)

        agent_report = _parse_agent_report(d.pop("agent_report"))

        def _parse_decided_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                decided_at_type_0 = datetime.datetime.fromisoformat(data)

                return decided_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        decided_at = _parse_decided_at(d.pop("decided_at"))

        def _parse_decision(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        decision = _parse_decision(d.pop("decision"))

        def _parse_notes(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        notes = _parse_notes(d.pop("notes"))

        def _parse_reviewer(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        reviewer = _parse_reviewer(d.pop("reviewer"))

        step = d.pop("step")

        review_view = cls(
            agent_report=agent_report,
            decided_at=decided_at,
            decision=decision,
            notes=notes,
            reviewer=reviewer,
            step=step,
        )

        review_view.additional_properties = d
        return review_view

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
