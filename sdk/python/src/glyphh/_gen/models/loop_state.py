from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.loop_state_engine import LoopStateEngine

T = TypeVar("T", bound="LoopState")


@_attrs_define
class LoopState:
    """
    Attributes:
        account (None | str):
        engine (LoopStateEngine):
        login_step (None | str):
        models (int | None):
        ready (bool):
        signed_in (bool | None):
        version (None | str):
    """

    account: str | None
    engine: LoopStateEngine
    login_step: str | None
    models: int | None
    ready: bool
    signed_in: bool | None
    version: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account: str | None
        account = self.account

        engine = self.engine.value

        login_step: str | None
        login_step = self.login_step

        models: int | None
        models = self.models

        ready = self.ready

        signed_in: bool | None
        signed_in = self.signed_in

        version: str | None
        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account": account,
                "engine": engine,
                "login_step": login_step,
                "models": models,
                "ready": ready,
                "signed_in": signed_in,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_account(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        account = _parse_account(d.pop("account"))

        engine = LoopStateEngine(d.pop("engine"))

        def _parse_login_step(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        login_step = _parse_login_step(d.pop("login_step"))

        def _parse_models(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        models = _parse_models(d.pop("models"))

        ready = d.pop("ready")

        def _parse_signed_in(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        signed_in = _parse_signed_in(d.pop("signed_in"))

        def _parse_version(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        version = _parse_version(d.pop("version"))

        loop_state = cls(
            account=account,
            engine=engine,
            login_step=login_step,
            models=models,
            ready=ready,
            signed_in=signed_in,
            version=version,
        )

        loop_state.additional_properties = d
        return loop_state

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
