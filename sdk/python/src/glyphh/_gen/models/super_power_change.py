from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.super_power_change_effort_type_0 import SuperPowerChangeEffortType0
from ..models.super_power_change_role_type_0 import SuperPowerChangeRoleType0
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.super_power_change_map_layout_type_0 import SuperPowerChangeMapLayoutType0


T = TypeVar("T", bound="SuperPowerChange")


@_attrs_define
class SuperPowerChange:
    """
    Attributes:
        avatar_color (None | str | Unset):
        avatar_variant (int | None | Unset):
        description (None | str | Unset):
        directness (int | None | Unset):
        effort (None | SuperPowerChangeEffortType0 | Unset):
        instructions (None | str | Unset):
        listen_model_id (None | Unset | UUID):
        live (bool | None | Unset):
        map_layout (None | SuperPowerChangeMapLayoutType0 | Unset):
        name (None | str | Unset):
        personality (int | None | Unset):
        role (None | SuperPowerChangeRoleType0 | Unset):
        temperament (int | None | Unset):
        voice_id (None | str | Unset):
        voice_model_id (None | Unset | UUID):
        voice_name (None | str | Unset):
    """

    avatar_color: str | Unset | None = UNSET
    avatar_variant: int | Unset | None = UNSET
    description: str | Unset | None = UNSET
    directness: int | Unset | None = UNSET
    effort: SuperPowerChangeEffortType0 | Unset | None = UNSET
    instructions: str | Unset | None = UNSET
    listen_model_id: Unset | UUID | None = UNSET
    live: bool | Unset | None = UNSET
    map_layout: SuperPowerChangeMapLayoutType0 | Unset | None = UNSET
    name: str | Unset | None = UNSET
    personality: int | Unset | None = UNSET
    role: SuperPowerChangeRoleType0 | Unset | None = UNSET
    temperament: int | Unset | None = UNSET
    voice_id: str | Unset | None = UNSET
    voice_model_id: Unset | UUID | None = UNSET
    voice_name: str | Unset | None = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.super_power_change_map_layout_type_0 import SuperPowerChangeMapLayoutType0

        avatar_color: str | Unset | None
        if isinstance(self.avatar_color, Unset):
            avatar_color = UNSET
        else:
            avatar_color = self.avatar_color

        avatar_variant: int | Unset | None
        if isinstance(self.avatar_variant, Unset):
            avatar_variant = UNSET
        else:
            avatar_variant = self.avatar_variant

        description: str | Unset | None
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        directness: int | Unset | None
        if isinstance(self.directness, Unset):
            directness = UNSET
        else:
            directness = self.directness

        effort: str | Unset | None
        if isinstance(self.effort, Unset):
            effort = UNSET
        elif isinstance(self.effort, SuperPowerChangeEffortType0):
            effort = self.effort.value
        else:
            effort = self.effort

        instructions: str | Unset | None
        if isinstance(self.instructions, Unset):
            instructions = UNSET
        else:
            instructions = self.instructions

        listen_model_id: str | Unset | None
        if isinstance(self.listen_model_id, Unset):
            listen_model_id = UNSET
        elif isinstance(self.listen_model_id, UUID):
            listen_model_id = str(self.listen_model_id)
        else:
            listen_model_id = self.listen_model_id

        live: bool | Unset | None
        if isinstance(self.live, Unset):
            live = UNSET
        else:
            live = self.live

        map_layout: dict[str, Any] | Unset | None
        if isinstance(self.map_layout, Unset):
            map_layout = UNSET
        elif isinstance(self.map_layout, SuperPowerChangeMapLayoutType0):
            map_layout = self.map_layout.to_dict()
        else:
            map_layout = self.map_layout

        name: str | Unset | None
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        personality: int | Unset | None
        if isinstance(self.personality, Unset):
            personality = UNSET
        else:
            personality = self.personality

        role: str | Unset | None
        if isinstance(self.role, Unset):
            role = UNSET
        elif isinstance(self.role, SuperPowerChangeRoleType0):
            role = self.role.value
        else:
            role = self.role

        temperament: int | Unset | None
        if isinstance(self.temperament, Unset):
            temperament = UNSET
        else:
            temperament = self.temperament

        voice_id: str | Unset | None
        if isinstance(self.voice_id, Unset):
            voice_id = UNSET
        else:
            voice_id = self.voice_id

        voice_model_id: str | Unset | None
        if isinstance(self.voice_model_id, Unset):
            voice_model_id = UNSET
        elif isinstance(self.voice_model_id, UUID):
            voice_model_id = str(self.voice_model_id)
        else:
            voice_model_id = self.voice_model_id

        voice_name: str | Unset | None
        if isinstance(self.voice_name, Unset):
            voice_name = UNSET
        else:
            voice_name = self.voice_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if avatar_color is not UNSET:
            field_dict["avatar_color"] = avatar_color
        if avatar_variant is not UNSET:
            field_dict["avatar_variant"] = avatar_variant
        if description is not UNSET:
            field_dict["description"] = description
        if directness is not UNSET:
            field_dict["directness"] = directness
        if effort is not UNSET:
            field_dict["effort"] = effort
        if instructions is not UNSET:
            field_dict["instructions"] = instructions
        if listen_model_id is not UNSET:
            field_dict["listen_model_id"] = listen_model_id
        if live is not UNSET:
            field_dict["live"] = live
        if map_layout is not UNSET:
            field_dict["map_layout"] = map_layout
        if name is not UNSET:
            field_dict["name"] = name
        if personality is not UNSET:
            field_dict["personality"] = personality
        if role is not UNSET:
            field_dict["role"] = role
        if temperament is not UNSET:
            field_dict["temperament"] = temperament
        if voice_id is not UNSET:
            field_dict["voice_id"] = voice_id
        if voice_model_id is not UNSET:
            field_dict["voice_model_id"] = voice_model_id
        if voice_name is not UNSET:
            field_dict["voice_name"] = voice_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.super_power_change_map_layout_type_0 import SuperPowerChangeMapLayoutType0

        d = dict(src_dict)

        def _parse_avatar_color(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        avatar_color = _parse_avatar_color(d.pop("avatar_color", UNSET))

        def _parse_avatar_variant(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        avatar_variant = _parse_avatar_variant(d.pop("avatar_variant", UNSET))

        def _parse_description(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_directness(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        directness = _parse_directness(d.pop("directness", UNSET))

        def _parse_effort(data: object) -> SuperPowerChangeEffortType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                effort_type_0 = SuperPowerChangeEffortType0(data)

                return effort_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SuperPowerChangeEffortType0 | Unset, data)

        effort = _parse_effort(d.pop("effort", UNSET))

        def _parse_instructions(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        instructions = _parse_instructions(d.pop("instructions", UNSET))

        def _parse_listen_model_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                listen_model_id_type_0 = UUID(data)

                return listen_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        listen_model_id = _parse_listen_model_id(d.pop("listen_model_id", UNSET))

        def _parse_live(data: object) -> bool | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        live = _parse_live(d.pop("live", UNSET))

        def _parse_map_layout(data: object) -> SuperPowerChangeMapLayoutType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                map_layout_type_0 = SuperPowerChangeMapLayoutType0.from_dict(data)

                return map_layout_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SuperPowerChangeMapLayoutType0 | Unset, data)

        map_layout = _parse_map_layout(d.pop("map_layout", UNSET))

        def _parse_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_personality(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        personality = _parse_personality(d.pop("personality", UNSET))

        def _parse_role(data: object) -> SuperPowerChangeRoleType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                role_type_0 = SuperPowerChangeRoleType0(data)

                return role_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SuperPowerChangeRoleType0 | Unset, data)

        role = _parse_role(d.pop("role", UNSET))

        def _parse_temperament(data: object) -> int | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        temperament = _parse_temperament(d.pop("temperament", UNSET))

        def _parse_voice_id(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        voice_id = _parse_voice_id(d.pop("voice_id", UNSET))

        def _parse_voice_model_id(data: object) -> Unset | UUID | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                voice_model_id_type_0 = UUID(data)

                return voice_model_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        voice_model_id = _parse_voice_model_id(d.pop("voice_model_id", UNSET))

        def _parse_voice_name(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        voice_name = _parse_voice_name(d.pop("voice_name", UNSET))

        super_power_change = cls(
            avatar_color=avatar_color,
            avatar_variant=avatar_variant,
            description=description,
            directness=directness,
            effort=effort,
            instructions=instructions,
            listen_model_id=listen_model_id,
            live=live,
            map_layout=map_layout,
            name=name,
            personality=personality,
            role=role,
            temperament=temperament,
            voice_id=voice_id,
            voice_model_id=voice_model_id,
            voice_name=voice_name,
        )

        super_power_change.additional_properties = d
        return super_power_change

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
