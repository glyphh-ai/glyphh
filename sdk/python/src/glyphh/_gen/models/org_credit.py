from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.credit import Credit


T = TypeVar("T", bound="OrgCredit")


@_attrs_define
class OrgCredit:
    """What any member sees of their org's billing (the Account page): the plan, when it renews, the credit.

    Attributes:
        credit (Credit):
        plan (str):
        renews_at (datetime.datetime | None):
    """

    credit: Credit
    plan: str
    renews_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        credit = self.credit.to_dict()

        plan = self.plan

        renews_at: str | None
        if isinstance(self.renews_at, datetime.datetime):
            renews_at = self.renews_at.isoformat()
        else:
            renews_at = self.renews_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "credit": credit,
                "plan": plan,
                "renews_at": renews_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credit import Credit

        d = dict(src_dict)
        credit = Credit.from_dict(d.pop("credit"))

        plan = d.pop("plan")

        def _parse_renews_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                renews_at_type_0 = datetime.datetime.fromisoformat(data)

                return renews_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        renews_at = _parse_renews_at(d.pop("renews_at"))

        org_credit = cls(
            credit=credit,
            plan=plan,
            renews_at=renews_at,
        )

        org_credit.additional_properties = d
        return org_credit

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
