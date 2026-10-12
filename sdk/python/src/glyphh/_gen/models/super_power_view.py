from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.grant_view import GrantView
    from ..models.loop_view import LoopView
    from ..models.super_power_view_map_layout import SuperPowerViewMapLayout


T = TypeVar("T", bound="SuperPowerView")


@_attrs_define
class SuperPowerView:
    """
    Attributes:
        avatar_color (None | str):
        avatar_variant (int):
        description (str):
        directness (int):
        effort (None | str):
        glyphh (bool):
        grants (list[GrantView]):
        id (UUID):
        instructions (str):
        listen_model_id (None | UUID):
        live (bool):
        loop (LoopView | None):
        machines (list[str]):
        map_layout (SuperPowerViewMapLayout):
        name (str):
        personality (int):
        role (str):
        temperament (int):
        updated_at (datetime.datetime):
        voice_id (None | str):
        voice_model_id (None | UUID):
        voice_name (None | str):
    """

    avatar_color: str | None
    avatar_variant: int
    description: str
    directness: int
    effort: str | None
    glyphh: bool
    grants: list[GrantView]
    id: UUID
    instructions: str
    listen_model_id: UUID | None
    live: bool
    loop: LoopView | None
    machines: list[str]
    map_layout: SuperPowerViewMapLayout
    name: str
    personality: int
    role: str
    temperament: int
    updated_at: datetime.datetime
    voice_id: str | None
    voice_model_id: UUID | None
    voice_name: str | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.loop_view import LoopView

        avatar_color: str | None
        avatar_color = self.avatar_color

        avatar_variant = self.avatar_variant

        description = self.description

        directness = self.directness

        effort: str | None
        effort = self.effort

        glyphh = self.glyphh

        grants = []
        for grants_item_data in self.grants:
            grants_item = grants_item_data.to_dict()
            grants.append(grants_item)

        id = str(self.id)

        instructions = self.instructions

        listen_model_id: str | None
        if isinstance(self.listen_model_id, UUID):
            listen_model_id = str(self.listen_model_id)
        else:
            listen_model_id = self.listen_model_id

        live = self.live

        loop: dict[str, Any] | None
        if isinstance(self.loop, LoopView):
            loop = self.loop.to_dict()
        else:
            loop = self.loop

        machines = self.machines

        map_layout = self.map_layout.to_dict()

        name = self.name

        personality = self.personality

        role = self.role

        temperament = self.temperament

        updated_at = self.updated_at.isoformat()

        voice_id: str | None
        voice_id = self.voice_id

        voice_model_id: str | None
        if isinstance(self.voice_model_id, UUID):
            voice_model_id = str(self.voice_model_id)
        else:
            voice_model_id = self.voice_model_id

        voice_name: str | None
        voice_name = self.voice_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "avatar_color": avatar_color,
                "avatar_variant": avatar_variant,
                "description": description,
                "directness": directness,
                "effort": effort,
                "glyphh": glyphh,
                "grants": grants,
                "id": id,
                "instructions": instructions,
                "listen_model_id": listen_model_id,
                "live": live,
                "loop": loop,
                "machines": machines,
                "map_layout": map_layout,
                "name": name,
                "personality": personality,
                "role": role,
                "temperament": temperament,
                "updated_at": updated_at,
                "voice_id": voice_id,
                "voice_model_id": voice_model_id,
                "voice_name": voice_name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.grant_view import GrantView
        from ..models.loop_view import LoopView
        from ..models.super_power_view_map_layout import SuperPowerViewMapLayout

        d = dict(src_dict)

        def _parse_avatar_color(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        avatar_color = _parse_avatar_color(d.pop("avatar_color"))

        avatar_variant = d.pop("avatar_variant")

        description = d.pop("description")

        directness = d.pop("directness")

        def _parse_effort(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        effort = _parse_effort(d.pop("effort"))

        glyphh = d.pop("glyphh")

        grants = []
        _grants = d.pop("grants")
        for grants_item_data in _grants:
            grants_item = GrantView.from_dict(grants_item_data)

            grants.append(grants_item)

        id = UUID(d.pop("id"))

        instructions = d.pop("instructions")

        def _parse_listen_model_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                listen_model_id_type_0 = UUID(data)

                return listen_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        listen_model_id = _parse_listen_model_id(d.pop("listen_model_id"))

        live = d.pop("live")

        def _parse_loop(data: object) -> LoopView | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                loop_type_0 = LoopView.from_dict(data)

                return loop_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(LoopView | None, data)

        loop = _parse_loop(d.pop("loop"))

        machines = cast(list[str], d.pop("machines"))

        map_layout = SuperPowerViewMapLayout.from_dict(d.pop("map_layout"))

        name = d.pop("name")

        personality = d.pop("personality")

        role = d.pop("role")

        temperament = d.pop("temperament")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        def _parse_voice_id(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        voice_id = _parse_voice_id(d.pop("voice_id"))

        def _parse_voice_model_id(data: object) -> UUID | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                voice_model_id_type_0 = UUID(data)

                return voice_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        voice_model_id = _parse_voice_model_id(d.pop("voice_model_id"))

        def _parse_voice_name(data: object) -> str | None:
            if data is None:
                return data
            return cast(None | str, data)

        voice_name = _parse_voice_name(d.pop("voice_name"))

        super_power_view = cls(
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            description=description,
            directness=directness,
            effort=effort,
            glyphh=glyphh,
            grants=grants,
            id=id,
            instructions=instructions,
            listen_model_id=listen_model_id,
            live=live,
            loop=loop,
            machines=machines,
            map_layout=map_layout,
            name=name,
            personality=personality,
            role=role,
            temperament=temperament,
            updated_at=updated_at,
            voice_id=voice_id,
            voice_model_id=voice_model_id,
            voice_name=voice_name,
        )

        super_power_view.additional_properties = d
        return super_power_view

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
