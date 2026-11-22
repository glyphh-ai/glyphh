"""A gate's item made readable for a person (docs/specs/bots.md, 12): its fields flattened to `name: text` (nested
names joined with a dot, lists of plain values joined), and its label, a title or summary drawn from those fields.
A label is never raw JSON: the runner's own label is kept only when it is not JSON."""

import json
from typing import Any

FIELDS_MAX: int = 40
VALUE_MAX: int = 2_000
LABEL_MAX: int = 140
# the fields a label is drawn from, the first one there (by its last name: user.login reads as login)
TITLES: tuple[str, ...] = ("title", "subject", "summary", "name", "headline", "label", "snippet", "text", "body")
SKIPPED: frozenset[str] = frozenset({"id", "node_id", "url", "key"})


def _plain(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int | float | str):
        text = str(value).strip()
        return text[:VALUE_MAX] if text else None
    return None


def _walk(value: Any, at: str, out: dict[str, str]) -> None:
    if len(out) >= FIELDS_MAX:
        return
    if isinstance(value, dict):
        for k, v in value.items():
            _walk(v, f"{at}.{k}" if at else str(k), out)
    elif isinstance(value, list):
        plain = [p for p in (_plain(v) for v in value) if p is not None]
        if plain and len(plain) == len(value):
            out[at or "value"] = ", ".join(plain)[:VALUE_MAX]
        else:
            for i, v in enumerate(value[:10]):
                _walk(v, f"{at}.{i + 1}" if at else str(i + 1), out)
    elif (shown := _plain(value)) is not None:
        out[at or "value"] = shown


def _common(names: list[str]) -> str:
    """The dotted start every name shares (a gate's case is {layer: {segment: {role: value}}})."""
    parts = [n.split(".")[:-1] for n in names]
    shared: list[str] = []
    for column in zip(*parts, strict=False):
        if len(set(column)) != 1:
            break
        shared.append(column[0])
    return ".".join(shared)


def fields(item: Any) -> dict[str, str]:
    """The item's fields as `name: text`, at most 40, each at most 2,000 characters; a start every name shares is
    left off (a case's layer and segment)."""
    out: dict[str, str] = {}
    _walk(item, "", out)
    cut = _common(list(out))
    return {k[len(cut) + 1 :]: v for k, v in out.items()} if cut else out


def _json_like(text: str) -> bool:
    t = text.strip()
    if not t or t[0] not in "{[":
        return False
    try:
        json.loads(t)
    except ValueError:
        return t.endswith("...")  # the runner's label is JSON cut at 120 characters
    return True


def _short(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= LABEL_MAX else line[: LABEL_MAX - 1] + "…"


def label(given: str | None, shown: dict[str, str]) -> str:
    """A title or summary for the item: the runner's label unless it is JSON, else its first title-like field, else
    its first few fields."""
    if given and not _json_like(given):
        return _short(given)
    last = {name.rsplit(".", 1)[-1].lower(): value for name, value in reversed(shown.items())}
    for name in TITLES:
        if last.get(name):
            return _short(last[name])
    plain = [(k, v) for k, v in shown.items() if k.rsplit(".", 1)[-1] not in SKIPPED]
    return _short(" · ".join(f"{k} {v}" for k, v in plain[:3])) if plain else "An item with no fields"


def body(shown_label: str, shown: dict[str, str], *more: str | None) -> str:
    """What the search reads: the label, every field's name and text, and the gate and outcomes."""
    words = [shown_label, *(f"{k} {v}" for k, v in shown.items()), *(m for m in more if m)]
    return "\n".join(words)[:20_000]
