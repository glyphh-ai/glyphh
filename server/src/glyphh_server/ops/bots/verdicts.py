"""The Resume Screener's verdicts as Gmail labels (ops/bots/builtins.py `inbox_label`). The bot's agent gives each
application one verdict from what its decisions said (spam when the sender is; else how well the applicant fits the
role: strong, borderline or poor) and hands them here: every screened message is labelled Screened, with its
verdict's label beside it; a message the sender checks refused counts as spam. One still waiting on a decision, and
an application the person handed in (no message), gets none."""

from typing import Any

LABELS: dict[str, str] = {
    "strong": "Screened/Strong", "borderline": "Screened/Borderline", "poor": "Screened/Poor", "spam": "Screened/Spam",
}  # fmt: skip
SCREENED: str = "Screened"
GIVEN: str = "given-"  # the id of an application the person handed in (ops/bots/builtins.py)


def _ids(given: Any) -> list[tuple[str, dict[str, Any]]]:
    """Each entry that names a message, with its id; anything else an agent might hand in is left out."""
    found = [e for e in given if isinstance(e, dict)] if isinstance(given, list) else []
    return [(str(e["id"]), e) for e in found if e.get("id") and not str(e["id"]).startswith(GIVEN)]


def marks(given: dict[str, Any]) -> dict[str, list[str]]:
    """The inbox labels for a run's verdicts, `{verdicts: [{id, verdict}], rejected: [{id}]}`: {label: message ids}."""
    out: dict[str, list[str]] = {SCREENED: [], **{name: [] for name in LABELS.values()}}
    for mid, v in _ids(given.get("verdicts")):
        if v.get("verdict") in LABELS:
            out[SCREENED].append(mid)
            out[LABELS[v["verdict"]]].append(mid)
    for mid, _ in _ids(given.get("rejected")):
        out[SCREENED].append(mid)
        out[LABELS["spam"]].append(mid)
    return {name: ids for name, ids in out.items() if ids}
