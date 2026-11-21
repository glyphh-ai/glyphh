"""The tools a bot's run offers Claude, and calling one. Only what the bot is let use: per connection, the Pipedream
actions its scope names (each named by its key, its input the action's props but the account, which the server fills
in with the connection's), and with any Ada models, ada_decide and ada_record over them, asked as the person who
started the run."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid
from glyphh_server.models import Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import props
from glyphh_server.ops.bots.pipedream import Pipedream
from glyphh_server.ops.templates.ada import ask

Call = Callable[[dict[str, Any]], Awaitable[Any]]
NAME_MAX: int = 64


@dataclass
class Offered:
    defs: list[dict[str, Any]] = field(default_factory=list)  # as Claude's tools parameter takes them
    calls: dict[str, tuple[str, Call]] = field(default_factory=dict)  # name: (step kind, its call)

    def add(self, kind: str, name: str, description: str, schema: dict[str, Any], call: Call) -> None:
        unique, n = name[:NAME_MAX], 2
        while unique in self.calls:
            unique, n = f"{name[: NAME_MAX - 4]}-{n}", n + 1
        self.defs.append({"name": unique, "description": description[:4000], "input_schema": schema})
        self.calls[unique] = (kind, call)

    async def call(self, name: str, given: dict[str, Any]) -> tuple[str, Any]:
        found = self.calls.get(name)
        if found is None:
            raise Invalid(f"The bot may not use {name!r}.", reason="tool")
        kind, call = found
        return kind, await call(given)


def _action(pd: Pipedream, org_id: uuid.UUID, key: str, defined: list[dict[str, Any]], account: str) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        return await pd.run(org_id, key, props.configured(defined, account, given))

    return call


async def _connections(engine: AsyncEngine, org_id: uuid.UUID, scopes: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [uuid.UUID(s["connection_id"]) for s in scopes]
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        return {str(r.id): r for r in await conn.execute(select(Connection).where(Connection.id.in_(ids)))}


async def pipedream_tools(offered: Offered, pd: Pipedream, engine: AsyncEngine, bot: Any) -> None:
    linked = await _connections(engine, bot.org_id, bot.scopes)
    for scope in bot.scopes:
        found = linked.get(scope["connection_id"])
        if found is None:  # the connection was removed since
            continue
        for key in scope["tools"]:
            component = await pd.component(key)
            defined = component.get("configurable_props") or []
            about = f"{component.get('description') or component.get('name') or key} (as {found.app_name}"
            about += f" {found.label})" if found.label else ")"
            offered.add(
                "tool", key, about, props.schema(defined), _action(pd, bot.org_id, key, defined, found.account_id)
            )


def _ada(state: Any, who: Principal, models: list[str], op: str) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        model = given.get("model")
        if model not in models:
            raise Invalid(f"The bot may ask only {', '.join(models)}.", reason="model")
        args = {"data": given.get("data") or {}}
        if op == "record":
            args["outcome"] = given.get("outcome")
        return await ask(state, who, model, op, args)

    return call


def _ada_schema(models: list[str], record: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "model": {"type": "string", "enum": models, "description": "The Ada model"},
        "data": {"type": "object", "description": "The case: its fields as the model's spec names them"},
    }
    if record:
        properties["outcome"] = {"description": "What was decided, or really happened, in the case"}
    return {"type": "object", "properties": properties, "required": list(properties)}


def ada_tools(offered: Offered, state: Any, who: Principal, models: list[str]) -> None:
    if not models or state is None:
        return
    decide = "Ask an Ada model to decide a case the way its precedents were decided: its answer and how sure it is."
    record = "Teach an Ada model a case and its outcome: a precedent its next decisions are made from."
    offered.add("ada", "ada_decide", decide, _ada_schema(models, False), _ada(state, who, models, "decide"))
    offered.add("ada", "ada_record", record, _ada_schema(models, True), _ada(state, who, models, "record"))


async def offered(pd: Pipedream, engine: AsyncEngine, ada: Any, who: Principal, bot: Any) -> Offered:
    made = Offered()
    if bot.scopes:
        await pipedream_tools(made, pd, engine, bot)
    ada_tools(made, ada, who, list(bot.models))
    return made
