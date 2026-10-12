from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.audit_entry_after import AuditEntryAfter
    from ..models.audit_entry_before import AuditEntryBefore


T = TypeVar("T", bound="AuditEntry")


@_attrs_define
class AuditEntry:
    """
    Attributes:
        action (str):
        after (AuditEntryAfter):
        at (datetime.datetime):
        before (AuditEntryBefore):
        id (UUID):
        org (None | str):
        region (None | str):
        role (str):
        source (str):
        source_detail (None | str):
        summary (str):
        target_id (None | str):
        target_kind (str):
        target_label (str):
        trace_id (None | str):
        type_ (str):
        who (str):
        who_id (None | UUID):
    """

    action: str
    after: AuditEntryAfter
    at: datetime.datetime
    before: AuditEntryBefore
    id: UUID
    org: str | None
    region: str | None
    role: str
    source: str
    source_detail: str | None
    summary: str
    target_id: str | None
    target_kind: str
    target_label: str
    trace_id: str | None
    type_: str
    who: str
    who_id: UUID | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        action = self.action

        after = self.after.to_dict()

        at = self.at.isoformat()

        before = self.before.to_dict()

        id = str(self.id)

        org: str | None
        org = self.org

        region: str | None
        region = self.region

        role = self.role

        source = self.source

        source_detail: str | None
        source_detail = self.source_detail

        summary = self.summary

        target_id: str | None
        target_id = self.target_id

        target_kind = self.target_kind

        target_label = self.target_label

        trace_id: str | None
        trace_id = self.trace_id

        type_ = self.type_

        who = self.who

        who_id: str | None
        if isinstance(self.who_id, UUID):
            who_id = str(self.who_id)
        else:
            who_id = self.who_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "action": action,
                "after": after,
                "at": at,
                "before": before,
                "id": id,
                "org": org,
                "region": region,
                "role": role,
                "source": source,
                "source_detail": source_detail,
                "summary": summary,
                "target_id": target_id,
                "target_kind": target_kind,
                "target_label": target_label,
                "trace_id": trace_id,
                "type": type_,
                "who": who,
                "who_id": who_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.audit_entry_after import AuditEntryAfter
        from ..models.audit_entry_before import AuditEntryBefore

        d = dict(src_dict)
        action = d.pop("action")

        after = AuditEntryAfter.from_dict(d.pop("after"))

        at = datetime.datetime.fromisoformat(d.pop("at"))

        before = AuditEntryBefore.from_dict(d.pop("before"))

        id = UUID(d.pop("id"))

        def _parse_org(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        org = _parse_org(d.pop("org"))

        def _parse_region(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        region = _parse_region(d.pop("region"))

        role = d.pop("role")

        source = d.pop("source")

        def _parse_source_detail(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        source_detail = _parse_source_detail(d.pop("source_detail"))

        summary = d.pop("summary")

        def _parse_target_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        target_id = _parse_target_id(d.pop("target_id"))

        target_kind = d.pop("target_kind")

        target_label = d.pop("target_label")

        def _parse_trace_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        trace_id = _parse_trace_id(d.pop("trace_id"))

        type_ = d.pop("type")

        who = d.pop("who")

        def _parse_who_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                who_id_type_0 = UUID(data)

                return who_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        who_id = _parse_who_id(d.pop("who_id"))

        audit_entry = cls(
            action=action,
            after=after,
            at=at,
            before=before,
            id=id,
            org=org,
            region=region,
            role=role,
            source=source,
            source_detail=source_detail,
            summary=summary,
            target_id=target_id,
            target_kind=target_kind,
            target_label=target_label,
            trace_id=trace_id,
            type_=type_,
            who=who,
            who_id=who_id,
        )

        audit_entry.additional_properties = d
        return audit_entry

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
