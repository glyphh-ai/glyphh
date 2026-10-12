from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.open_in_panel import OpenInPanel
from ..types import UNSET, Unset

T = TypeVar("T", bound="OpenIn")


@_attrs_define
class OpenIn:
    """
    Attributes:
        panel (OpenInPanel | Unset):  Default: OpenInPanel.MACHINE.
        super_power (None | Unset | UUID):
        thread (None | Unset | UUID):
    """

    panel: OpenInPanel | Unset = OpenInPanel.MACHINE
    super_power: Unset | UUID | None = UNSET
    thread: Unset | UUID | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        panel: str | Unset = UNSET
        if not isinstance(self.panel, Unset):
            panel = self.panel.value

        super_power: str | Unset | None
        if isinstance(self.super_power, Unset):
            super_power = UNSET
        elif isinstance(self.super_power, UUID):
            super_power = str(self.super_power)
        else:
            super_power = self.super_power

        thread: str | Unset | None
        if isinstance(self.thread, Unset):
            thread = UNSET
        elif isinstance(self.thread, UUID):
            thread = str(self.thread)
        else:
            thread = self.thread

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if panel is not UNSET:
            field_dict["panel"] = panel
        if super_power is not UNSET:
            field_dict["super_power"] = super_power
        if thread is not UNSET:
            field_dict["thread"] = thread

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _panel = d.pop("panel", UNSET)
        panel: OpenInPanel | Unset
        if isinstance(_panel, Unset):
            panel = UNSET
        else:
            panel = OpenInPanel(_panel)

        def _parse_super_power(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                super_power_type_0 = UUID(data)

                return super_power_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        super_power = _parse_super_power(d.pop("super_power", UNSET))

        def _parse_thread(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                thread_type_0 = UUID(data)

                return thread_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        thread = _parse_thread(d.pop("thread", UNSET))

        open_in = cls(
            panel=panel,
            super_power=super_power,
            thread=thread,
        )

        open_in.additional_properties = d
        return open_in

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
