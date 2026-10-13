from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.relay_call_mode import RelayCallMode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.relay_call_input import RelayCallInput


T = TypeVar("T", bound="RelayCall")


@_attrs_define
class RelayCall:
    """
    Attributes:
        connection_id (UUID):
        tool (str):
        input_ (RelayCallInput | Unset):
        mode (RelayCallMode | Unset):  Default: RelayCallMode.DRIVEN.
        run_id (None | Unset | UUID):
        super_power_id (None | Unset | UUID):
    """

    connection_id: UUID
    tool: str
    input_: RelayCallInput | Unset = UNSET
    mode: RelayCallMode | Unset = RelayCallMode.DRIVEN
    run_id: Unset | UUID | None = UNSET
    super_power_id: Unset | UUID | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        connection_id = str(self.connection_id)

        tool = self.tool

        input_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.input_, Unset):
            input_ = self.input_.to_dict()

        mode: str | Unset = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        run_id: str | Unset | None
        if isinstance(self.run_id, Unset):
            run_id = UNSET
        elif isinstance(self.run_id, UUID):
            run_id = str(self.run_id)
        else:
            run_id = self.run_id

        super_power_id: str | Unset | None
        if isinstance(self.super_power_id, Unset):
            super_power_id = UNSET
        elif isinstance(self.super_power_id, UUID):
            super_power_id = str(self.super_power_id)
        else:
            super_power_id = self.super_power_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "connection_id": connection_id,
                "tool": tool,
            }
        )
        if input_ is not UNSET:
            field_dict["input"] = input_
        if mode is not UNSET:
            field_dict["mode"] = mode
        if run_id is not UNSET:
            field_dict["run_id"] = run_id
        if super_power_id is not UNSET:
            field_dict["super_power_id"] = super_power_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.relay_call_input import RelayCallInput

        d = dict(src_dict)
        connection_id = UUID(d.pop("connection_id"))

        tool = d.pop("tool")

        _input_ = d.pop("input", UNSET)
        input_: RelayCallInput | Unset
        if isinstance(_input_, Unset):
            input_ = UNSET
        else:
            input_ = RelayCallInput.from_dict(_input_)

        _mode = d.pop("mode", UNSET)
        mode: RelayCallMode | Unset
        if isinstance(_mode, Unset):
            mode = UNSET
        else:
            mode = RelayCallMode(_mode)

        def _parse_run_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                run_id_type_0 = UUID(data)

                return run_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        run_id = _parse_run_id(d.pop("run_id", UNSET))

        def _parse_super_power_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                super_power_id_type_0 = UUID(data)

                return super_power_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        super_power_id = _parse_super_power_id(d.pop("super_power_id", UNSET))

        relay_call = cls(
            connection_id=connection_id,
            tool=tool,
            input_=input_,
            mode=mode,
            run_id=run_id,
            super_power_id=super_power_id,
        )

        relay_call.additional_properties = d
        return relay_call

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
