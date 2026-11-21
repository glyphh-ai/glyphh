"""A Pipedream action as a Claude tool: its configurable props (Pipedream's component definition) as the tool's JSON
Schema, the app prop left out (the server fills it with the connection's account), and a call's input as the props
Pipedream runs it with."""

from typing import Any

TYPES: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "boolean": {"type": "boolean"},
    "object": {"type": "object"},
    "any": {},
    "string[]": {"type": "array", "items": {"type": "string"}},
    "integer[]": {"type": "array", "items": {"type": "integer"}},
    "boolean[]": {"type": "array", "items": {"type": "boolean"}},
    "object[]": {"type": "array", "items": {"type": "object"}},
}


def app_prop(props: list[dict[str, Any]]) -> str | None:
    """The name of the prop that takes the account."""
    return next((p["name"] for p in props if p.get("type") == "app"), None)


def _enum(options: Any) -> list[Any] | None:
    if not isinstance(options, list) or not options:
        return None
    values = [o.get("value") if isinstance(o, dict) else o for o in options]
    return values if all(isinstance(v, (str, int, bool)) for v in values) else None


def _property(prop: dict[str, Any]) -> dict[str, Any] | None:
    kind = TYPES.get(str(prop.get("type", "")))
    if kind is None:  # alerts, interfaces, the app: nothing a caller fills in
        return None
    shown = dict(kind)
    words = " ".join(str(prop[k]) for k in ("label", "description") if prop.get(k))
    if words:
        shown["description"] = words[:1000]
    if (values := _enum(prop.get("options"))) is not None:
        shown["enum"] = values
    return shown


def schema(props: list[dict[str, Any]]) -> dict[str, Any]:
    """The tool's input schema."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for prop in props:
        shown = _property(prop)
        if shown is None or prop.get("hidden"):
            continue
        properties[prop["name"]] = shown
        if not prop.get("optional"):
            required.append(prop["name"])
    return {"type": "object", "properties": properties, "required": required}


def configured(props: list[dict[str, Any]], account_id: str, given: dict[str, Any]) -> dict[str, Any]:
    """What Pipedream runs the action with: the caller's values, and the account in the app prop."""
    out = {k: v for k, v in given.items() if k in {p["name"] for p in props}}
    if (name := app_prop(props)) is not None:
        out[name] = {"authProvisionId": account_id}
    return out
