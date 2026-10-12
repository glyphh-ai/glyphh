from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.thread_start_engine import ThreadStartEngine
from ..models.thread_start_mode import ThreadStartMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="ThreadStart")


@_attrs_define
class ThreadStart:
    """
    Attributes:
        prompt (str):
        crew (list[UUID] | Unset):
        engine (ThreadStartEngine | Unset):  Default: ThreadStartEngine.CLAUDE_CODE.
        mode (ThreadStartMode | Unset):  Default: ThreadStartMode.DRIVEN.
        model (None | str | Unset):
        super_power (None | Unset | UUID):
    """

    prompt: str
    crew: list[UUID] | Unset = UNSET
    engine: ThreadStartEngine | Unset = ThreadStartEngine.CLAUDE_CODE
    mode: ThreadStartMode | Unset = ThreadStartMode.DRIVEN
    model: str | Unset | None = UNSET
    super_power: Unset | UUID | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        prompt = self.prompt

        crew: list[str] | Unset = UNSET
        if not isinstance(self.crew, Unset):
            crew = []
            for crew_item_data in self.crew:
                crew_item = str(crew_item_data)
                crew.append(crew_item)

        engine: str | Unset = UNSET
        if not isinstance(self.engine, Unset):
            engine = self.engine.value

        mode: str | Unset = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        model: str | Unset | None
        if isinstance(self.model, Unset):
            model = UNSET
        else:
            model = self.model

        super_power: str | Unset | None
        if isinstance(self.super_power, Unset):
            super_power = UNSET
        elif isinstance(self.super_power, UUID):
            super_power = str(self.super_power)
        else:
            super_power = self.super_power

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "prompt": prompt,
            }
        )
        if crew is not UNSET:
            field_dict["crew"] = crew
        if engine is not UNSET:
            field_dict["engine"] = engine
        if mode is not UNSET:
            field_dict["mode"] = mode
        if model is not UNSET:
            field_dict["model"] = model
        if super_power is not UNSET:
            field_dict["super_power"] = super_power

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        prompt = d.pop("prompt")

        _crew = d.pop("crew", UNSET)
        crew: list[UUID] | Unset = UNSET
        if _crew is not UNSET:
            crew = []
            for crew_item_data in _crew:
                crew_item = UUID(crew_item_data)

                crew.append(crew_item)

        _engine = d.pop("engine", UNSET)
        engine: ThreadStartEngine | Unset
        if isinstance(_engine, Unset):
            engine = UNSET
        else:
            engine = ThreadStartEngine(_engine)

        _mode = d.pop("mode", UNSET)
        mode: ThreadStartMode | Unset
        if isinstance(_mode, Unset):
            mode = UNSET
        else:
            mode = ThreadStartMode(_mode)

        def _parse_model(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        model = _parse_model(d.pop("model", UNSET))

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

        thread_start = cls(
            prompt=prompt,
            crew=crew,
            engine=engine,
            mode=mode,
            model=model,
            super_power=super_power,
        )

        thread_start.additional_properties = d
        return thread_start

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
