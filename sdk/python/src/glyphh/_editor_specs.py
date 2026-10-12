"""Super powers, custom powers and schedules, as calls: the Super powers page and the editor (configuration, loop,
grants, my Glyphh), my skills, plugins, tasks and apps (their files, a task's flow and slots), and schedules.
Answers are the server's JSON as plain dicts."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.custom_powers import (
    change_custom_power,
    create_custom_power,
    delete_custom_file,
    delete_custom_power,
    get_custom_power,
    list_custom_powers,
    read_custom_file,
    save_task_flow,
    set_task_slots,
    task_slots,
    write_custom_file,
)
from glyphh._gen.api.schedules import add_schedule, change_schedule, delete_schedule, list_schedules
from glyphh._gen.api.super_powers import (
    change_super_power,
    create_super_power,
    delete_super_power,
    get_super_power,
    list_super_powers,
    my_glyphh,
    set_grant,
    set_loop,
)
from glyphh._gen.models import (
    CustomChange,
    FileText,
    Flow,
    GrantChange,
    ListCustomPowersKindType0,
    ListSuperPowersStatus,
    LoopChoice,
    NewCustom,
    NewSuperPower,
    ScheduleIn,
    Slots,
    SuperPowerChange,
)
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]


def _sp(sp_id: str) -> dict[str, Any]:
    return {"sp_id": UUID(sp_id)}


def _p(power_id: str) -> dict[str, Any]:
    return {"power_id": UUID(power_id)}


def _body(model: Any, data: dict[str, Any]) -> dict[str, Any]:
    return {"body": model.from_dict(data)}


SUPER_POWER_SPECS: dict[str, Callable[..., Spec]] = {
    "list": lambda q="", status="all", machine=None, page=1, size=12: (
        _call(list_super_powers),
        {
            "q": q,
            "status": ListSuperPowersStatus(status),
            "machine": UUID(machine) if machine else UNSET,
            "page": page,
            "size": size,
        },
    ),
    "create": lambda name, instructions, description="": (
        _call(create_super_power),
        _body(NewSuperPower, {"name": name, "instructions": instructions, "description": description}),
    ),
    "glyphh": lambda: (_call(my_glyphh), {}),
    "get": lambda sp_id: (_call(get_super_power), _sp(sp_id)),
    "change": lambda sp_id, **change: (_call(change_super_power), {**_sp(sp_id), **_body(SuperPowerChange, change)}),
    "delete": lambda sp_id: (_call(delete_super_power), _sp(sp_id)),
    "grant": lambda sp_id, **change: (_call(set_grant), {**_sp(sp_id), **_body(GrantChange, change)}),
    "set_loop": lambda sp_id, engine, model_id=None: (
        _call(set_loop),
        {**_sp(sp_id), **_body(LoopChoice, {"engine": engine, "model_id": model_id})},
    ),
}

CUSTOM_SPECS: dict[str, Callable[..., Spec]] = {
    "list": lambda kind=None, q="", page=1, size=25: (
        _call(list_custom_powers),
        {
            "kind": ListCustomPowersKindType0(kind) if kind else UNSET,
            "q": q,
            "page": page,
            "size": size,
        },
    ),
    "create": lambda kind, name, description="": (
        _call(create_custom_power),
        _body(NewCustom, {"kind": kind, "name": name, "description": description}),
    ),
    "get": lambda power_id: (_call(get_custom_power), _p(power_id)),
    "change": lambda power_id, **change: (_call(change_custom_power), {**_p(power_id), **_body(CustomChange, change)}),
    "delete": lambda power_id: (_call(delete_custom_power), _p(power_id)),
    "read_file": lambda power_id, path: (_call(read_custom_file), {**_p(power_id), "path": path}),
    "write_file": lambda power_id, path, content: (
        _call(write_custom_file),
        {**_p(power_id), **_body(FileText, {"path": path, "content": content})},
    ),
    "delete_file": lambda power_id, path: (_call(delete_custom_file), {**_p(power_id), "path": path}),
    "save_flow": lambda power_id, flow: (_call(save_task_flow), {**_p(power_id), **_body(Flow, flow)}),
    "slots": lambda power_id: (_call(task_slots), _p(power_id)),
    "set_slots": lambda power_id, slots: (_call(set_task_slots), {**_p(power_id), **_body(Slots, {"slots": slots})}),
}

SCHEDULE_SPECS: dict[str, Callable[..., Spec]] = {
    "list": lambda target=None: (_call(list_schedules), {"target": UUID(target) if target else UNSET}),
    "add": lambda **schedule: (_call(add_schedule), _body(ScheduleIn, schedule)),
    "change": lambda schedule_id, **schedule: (
        _call(change_schedule),
        {"schedule_id": UUID(schedule_id), **_body(ScheduleIn, schedule)},
    ),
    "delete": lambda schedule_id: (_call(delete_schedule), {"schedule_id": UUID(schedule_id)}),
}
