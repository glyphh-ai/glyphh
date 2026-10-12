"""My powers: the model catalog, my models on my own keys, folders and browser profiles, and what my teams let me
add. A key is posted straight to the server and never returned; answers are the server's JSON as plain dicts."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._connection_specs import CONNECTION_SPECS
from glyphh._gen.api.powers import (
    add_browser,
    add_folder,
    add_model,
    check_model_key,
    delete_browser,
    delete_model,
    list_browsers,
    list_catalog_models,
    list_folders,
    list_models,
    list_providers,
    remove_folder,
    replace_model_key,
    what_i_can_add,
)
from glyphh._gen.models.key_in import KeyIn
from glyphh._gen.models.new_browser import NewBrowser
from glyphh._gen.models.new_folder import NewFolder
from glyphh._gen.models.new_model import NewModel
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]


def _id(power_id: str) -> dict[str, Any]:
    return {"power_id": UUID(power_id)}


SPECS: dict[str, Callable[..., Spec]] = {
    "providers": lambda q="": (_call(list_providers), {"q": q}),
    "catalog_models": lambda provider=None, q="", page=1, size=25: (
        _call(list_catalog_models),
        {"provider": provider or UNSET, "q": q, "page": page, "size": size},
    ),
    "models": lambda: (_call(list_models), {}),
    "add_model": lambda **body: (
        _call(add_model),
        {"body": NewModel.from_dict({k: v for k, v in body.items() if v is not None})},
    ),
    "replace_key": lambda power_id, api_key: (
        _call(replace_model_key),
        {**_id(power_id), "body": KeyIn(api_key=api_key)},
    ),
    "check_key": lambda power_id: (_call(check_model_key), _id(power_id)),
    "delete_model": lambda power_id: (_call(delete_model), _id(power_id)),
    "folders": lambda: (_call(list_folders), {}),
    "add_folder": lambda machine_id, path: (
        _call(add_folder),
        {"body": NewFolder.from_dict({"machine_id": machine_id, "path": path})},
    ),
    "remove_folder": lambda power_id: (_call(remove_folder), _id(power_id)),
    "browsers": lambda: (_call(list_browsers), {}),
    "add_browser": lambda name, machine_id, super_power_id: (
        _call(add_browser),
        {"body": NewBrowser.from_dict({"name": name, "machine_id": machine_id, "super_power_id": super_power_id})},
    ),
    "delete_browser": lambda power_id: (_call(delete_browser), _id(power_id)),
    "can_add": lambda: (_call(what_i_can_add), {}),
    **CONNECTION_SPECS,
}


class SpecApi:
    """Calls named by a table of specs: each name builds the generated operation and its arguments."""

    def __init__(self, run: Callable[..., Any], specs: dict[str, Callable[..., Spec]]) -> None:
        self._run = run
        self._specs = specs

    def __getattr__(self, name: str) -> Callable[..., Any]:
        spec = self._specs.get(name) if name != "_specs" else None
        if spec is None:
            raise AttributeError(name)

        def call(*args: Any, **kwargs: Any) -> Any:
            operation, params = spec(*args, **kwargs)
            return self._run(operation, **params)

        return call


class AsyncSpecApi(SpecApi):
    """The same calls, awaited."""

    def __getattr__(self, name: str) -> Callable[..., Any]:
        spec = self._specs.get(name) if name != "_specs" else None
        if spec is None:
            raise AttributeError(name)

        async def call(*args: Any, **kwargs: Any) -> Any:
            operation, params = spec(*args, **kwargs)
            return await self._run(operation, **params)

        return call


class Powers(SpecApi):
    """`Glyphh(...).powers`: providers, catalog_models, models, add_model, replace_key, check_key, delete_model,
    folders, add_folder, remove_folder, browsers, add_browser, delete_browser, can_add, services, connections,
    connect, reconnect, check_connection, disconnect, tools, set_tools."""

    def __init__(self, run: Callable[..., Any]) -> None:
        super().__init__(run, SPECS)


class AsyncPowers(AsyncSpecApi):
    def __init__(self, run: Callable[..., Awaitable[Any]]) -> None:
        super().__init__(run, SPECS)
