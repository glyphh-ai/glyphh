from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.machine_says import MachineSays


T = TypeVar("T", bound="Trade")


@_attrs_define
class Trade:
    """
    Attributes:
        code (str):
        machine (MachineSays | None | Unset):
    """

    code: str
    machine: MachineSays | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.machine_says import MachineSays

        code = self.code

        machine: dict[str, Any] | Unset | None
        if isinstance(self.machine, Unset):
            machine = UNSET
        elif isinstance(self.machine, MachineSays):
            machine = self.machine.to_dict()
        else:
            machine = self.machine

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "code": code,
            }
        )
        if machine is not UNSET:
            field_dict["machine"] = machine

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.machine_says import MachineSays

        d = dict(src_dict)
        code = d.pop("code")

        def _parse_machine(data: object) -> MachineSays | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                machine_type_0 = MachineSays.from_dict(data)

                return machine_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(MachineSays | None | Unset, data)

        machine = _parse_machine(d.pop("machine", UNSET))

        trade = cls(
            code=code,
            machine=machine,
        )

        trade.additional_properties = d
        return trade

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
