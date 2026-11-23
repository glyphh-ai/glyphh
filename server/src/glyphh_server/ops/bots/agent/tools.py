"""The tools a bot's agent has, and nothing else (docs/specs/bot-agent-loop.md, 3): each tool its connections' scope
names (a Pipedream action, described by its component: its name, what it does, its props as a JSON schema, the app
prop left out), `fetch` when the bot names hosts, Glyphh's own built-ins it names, `decide` (Ada) when it has
decisions, and `ask_person`. A tool is read-only when its component says so, else by its key's verb; read-only tools
never ask unless their connection says to."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Connection
from glyphh_server.ops.bots import builtins, props
from glyphh_server.ops.bots.pipedream import Pipedream

Call = Callable[[dict[str, Any]], Awaitable[Any]]
DECIDE: str = "decide"
ASK: str = "ask_person"
FETCH: str = "fetch"
READS: frozenset[str] = frozenset(
    {"get", "list", "find", "search", "read", "retrieve", "fetch", "check", "view", "watch", "count", "lookup"}
    | {"download", "export"}
)
BUILT_IN: dict[str, tuple[str, str, bool]] = builtins.ABOUT
TYPES: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "boolean": {"type": "boolean"},
    "object": {"type": "object"},
    "string[]": {"type": "array", "items": {"type": "string"}},
    "integer[]": {"type": "array", "items": {"type": "integer"}},
}
ANY: dict[str, Any] = {"type": "object", "properties": {}}


@dataclass(frozen=True)
class Tool:
    name: str  # as the agent calls it
    key: str  # as the server and the bot's scope name it
    title: str  # in plain words, for the person
    description: str
    schema: dict[str, Any]
    read_only: bool
    app: str = ""  # its app's name, when it is a connection's
    permission: str | None = None  # its connection's say: allow, ask, deny, or never set
    call: Call | None = field(default=None, compare=False)
    seconds: float = 120.0  # how long a call may take


def named(key: str) -> str:
    """A tool's key as the agent calls it: lower case, `_` for every other character."""
    return "".join(c if c.isalnum() else "_" for c in key.lower())


def reads(key: str, component: dict[str, Any]) -> bool:
    """Whether a connection's tool only reads: its component's own say, else its key's verb."""
    hinted = (component.get("annotations") or {}).get("readOnlyHint")
    if isinstance(hinted, bool):
        return hinted
    verb = key.split("-", 2)[1:2]
    return bool(verb) and verb[0] in READS


def _options(given: Any) -> list[Any]:
    return [o.get("value") if isinstance(o, dict) else o for o in given]


def schema(defined: list[dict[str, Any]]) -> dict[str, Any]:
    """A component's props as the JSON schema of its input: the app prop (the account) and what is only shown left
    out; an unknown type taken as text."""
    shown, required = {}, []
    for p in defined:
        if p.get("type") in ("app", "alert") or p.get("hidden"):
            continue
        said = dict(TYPES.get(str(p.get("type")), TYPES["string"]))
        about = " ".join(str(p[k]) for k in ("label", "description") if p.get(k))
        if about:
            said["description"] = about[:600]
        if isinstance(p.get("options"), list) and p["options"] and said.get("type") == "string":
            said["enum"] = _options(p["options"])
        shown[p["name"]] = said
        if not p.get("optional"):
            required.append(p["name"])
    return {"type": "object", "properties": shown, "required": required}


def _action(pd: Pipedream, org_id: uuid.UUID, key: str, defined: list[dict[str, Any]], account: str) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        return props.returned(await pd.run(org_id, key, props.configured(defined, account, given)))

    return call


def _about(decisions: dict[str, Any]) -> str:
    return "; ".join(
        f"{n}: {d.get('question') or n} ({', '.join(map(str, d.get('outcomes') or []))})" for n, d in decisions.items()
    )


def _items(decisions: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": {"type": "string", "enum": list(decisions)},
        "items": {"type": "array", "items": {"type": "object"}, "description": "The items, each with an id"},
    }


def deciding(decisions: dict[str, Any]) -> Tool:
    """`decide`: Ada's answer, item by item, from how the person decided items like these before."""
    said = (
        "Ask Ada how the person decided items like these before. Give the decision's name and the items, each an "
        "object with an id and the fields you have of it; get back, for each, Ada's outcome (null when it has "
        "nothing to go on), how sure it is, and `sure`: whether that is sure enough by the decision's own bar. Use "
        f"it as your instructions say. The decisions: {_about(decisions)}."
    )
    takes = {"type": "object", "properties": _items(decisions), "required": ["decision", "items"]}
    return Tool(DECIDE, DECIDE, "Decide", said, takes, True)


def asking(decisions: dict[str, Any]) -> Tool:
    """`ask_person`: the run stops with a question for the person, and carries on with their answer. About a
    decision's items, their answers teach that decision's Ada model."""
    said = (
        "Ask the person something and wait for their answer: give the question and, when they should pick, the "
        "options. To ask them how to decide items (and teach Ada their answers), give the decision's name and the "
        "items instead of options. After calling it, stop: you will be told their answer."
    )
    shape: dict[str, Any] = {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}}
    if decisions:
        said, shape = f"{said} The decisions: {_about(decisions)}.", shape | _items(decisions)
    return Tool(ASK, ASK, "Ask you", said, {"type": "object", "properties": shape, "required": ["question"]}, True)


def _fetch(hosts: list[str], call: Call) -> Tool:
    said = f"GET JSON from one of {', '.join(hosts)} (https). Takes url, and headers when the API needs them."
    takes = {
        "type": "object",
        "properties": {"url": {"type": "string"}, "headers": {"type": "object"}},
        "required": ["url"],
    }
    return Tool(FETCH, FETCH, "Read a page", said, takes, True, call=call)


async def _connected(pd: Pipedream, conn: AsyncConnection, bot: Any) -> tuple[list[Tool], str | None]:
    """The bot's connections' tools, and its first Gmail account (the built-ins')."""
    ids = [uuid.UUID(s["connection_id"]) for s in bot.scopes]
    linked = {str(r.id): r for r in await conn.execute(select(Connection).where(Connection.id.in_(ids)))} if ids else {}
    gmail = next((r.account_id for s in bot.scopes if (r := linked.get(s["connection_id"])) and r.app == "gmail"), None)
    found: list[Tool] = []
    for scope in bot.scopes:
        c = linked.get(scope["connection_id"])
        for key in scope["tools"] if c is not None else []:
            component = await pd.component(key)
            defined = component.get("configurable_props") or []
            found.append(
                Tool(
                    name=named(key),
                    key=key,
                    title=str(component.get("name") or key),
                    description=str(component.get("description") or component.get("name") or key)[:1000],
                    schema=schema(defined),
                    read_only=reads(key, component),
                    app=c.app_name,
                    permission=c.permissions.get(key),
                    call=_action(pd, bot.org_id, key, defined, c.account_id),
                )
            )
    return found, gmail


async def of(pd: Pipedream, conn: AsyncConnection, bot: Any, fetch: Call) -> dict[str, Tool]:
    """Every tool the bot's agent has, by the name the agent calls it."""
    found, gmail = await _connected(pd, conn, bot)
    hosts = [h for h in bot.spec.get("hosts") or [] if isinstance(h, str)]
    if hosts:
        found.append(_fetch(hosts, fetch))
    own = builtins.made(pd, bot.org_id, gmail)
    for name in bot.spec.get("builtins") or []:
        if name in BUILT_IN:
            title, about, read_only = BUILT_IN[name]
            found.append(Tool(name, name, title, about, ANY, read_only, call=own[name]))
    decisions = bot.spec.get("gates") if isinstance(bot.spec.get("gates"), dict) else {}  # `gates`: a storage name
    if decisions:
        found.append(deciding(decisions))
    found.append(asking(decisions))
    return {t.name: t for t in found}
