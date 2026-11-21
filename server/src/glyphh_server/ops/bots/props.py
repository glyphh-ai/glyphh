"""A Pipedream action's input as the props Pipedream runs it with: the caller's values (only the props the action's
component defines), and the connection's account in its app prop."""

from typing import Any


def app_prop(props: list[dict[str, Any]]) -> str | None:
    """The name of the prop that takes the account."""
    return next((p["name"] for p in props if p.get("type") == "app"), None)


def configured(props: list[dict[str, Any]], account_id: str, given: dict[str, Any]) -> dict[str, Any]:
    """What Pipedream runs the action with: the caller's values, and the account in the app prop."""
    out = {k: v for k, v in given.items() if k in {p["name"] for p in props}}
    if (name := app_prop(props)) is not None:
        out[name] = {"authProvisionId": account_id}
    return out
