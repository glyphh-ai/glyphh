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


def returned(ran: Any) -> Any:
    """What an action answered, its list where it is one: Gmail's Find Email answers its messages as a list, but as
    `{messages, truncated, note}` when they were cut to fit, so a loop's `$step.ret` is the list either way (the
    note kept beside it, `ret_note`)."""
    ret = ran.get("ret") if isinstance(ran, dict) else None
    if isinstance(ret, dict) and ret.get("truncated") and isinstance(ret.get("messages"), list):
        return {**ran, "ret": ret["messages"], "ret_note": str(ret.get("note") or "")}
    return ran
