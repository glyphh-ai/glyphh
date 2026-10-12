from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.plan_preview_kind import PlanPreviewKind

if TYPE_CHECKING:
    from ..models.plan_view import PlanView


T = TypeVar("T", bound="PlanPreview")


@_attrs_define
class PlanPreview:
    """
    Attributes:
        applies_at (datetime.datetime | None):
        current (PlanView):
        due_now_cents (int):
        kind (PlanPreviewKind):
        next_invoice_at (datetime.datetime | None):
        next_invoice_cents (int):
        seats (int):
        target (PlanView):
    """

    applies_at: datetime.datetime | None
    current: PlanView
    due_now_cents: int
    kind: PlanPreviewKind
    next_invoice_at: datetime.datetime | None
    next_invoice_cents: int
    seats: int
    target: PlanView
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        applies_at: str | None
        if isinstance(self.applies_at, datetime.datetime):
            applies_at = self.applies_at.isoformat()
        else:
            applies_at = self.applies_at

        current = self.current.to_dict()

        due_now_cents = self.due_now_cents

        kind = self.kind.value

        next_invoice_at: str | None
        if isinstance(self.next_invoice_at, datetime.datetime):
            next_invoice_at = self.next_invoice_at.isoformat()
        else:
            next_invoice_at = self.next_invoice_at

        next_invoice_cents = self.next_invoice_cents

        seats = self.seats

        target = self.target.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "applies_at": applies_at,
                "current": current,
                "due_now_cents": due_now_cents,
                "kind": kind,
                "next_invoice_at": next_invoice_at,
                "next_invoice_cents": next_invoice_cents,
                "seats": seats,
                "target": target,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plan_view import PlanView

        d = dict(src_dict)

        def _parse_applies_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                applies_at_type_0 = datetime.datetime.fromisoformat(data)

                return applies_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        applies_at = _parse_applies_at(d.pop("applies_at"))

        current = PlanView.from_dict(d.pop("current"))

        due_now_cents = d.pop("due_now_cents")

        kind = PlanPreviewKind(d.pop("kind"))

        def _parse_next_invoice_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_invoice_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_invoice_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        next_invoice_at = _parse_next_invoice_at(d.pop("next_invoice_at"))

        next_invoice_cents = d.pop("next_invoice_cents")

        seats = d.pop("seats")

        target = PlanView.from_dict(d.pop("target"))

        plan_preview = cls(
            applies_at=applies_at,
            current=current,
            due_now_cents=due_now_cents,
            kind=kind,
            next_invoice_at=next_invoice_at,
            next_invoice_cents=next_invoice_cents,
            seats=seats,
            target=target,
        )

        plan_preview.additional_properties = d
        return plan_preview

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
