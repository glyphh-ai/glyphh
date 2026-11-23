"""A bot's use of the files in its folders, on its rrotor (docs/specs/bots.md, 14). The files are the machine's and
what is in them never comes here: the rrotor's glyphh_bot gives Claude tools over exactly the bot's folders, and
this server keeps names alone. Three things are its to do:

- say which rrotors do it (`uses`: rrotor 0.8.0; an older one keeps the single request a step was);
- hold the bot's permission to change a file (`file_change`, a tool the rrotor calls before each write or move, with
  the change's action and names): allowed at once unless the bot asks first, and then only by taking the person's
  yes to that very change, once (ops/bots/approvals.py);
- keep, with the run, the names of the files it read and changed (`data._files`, the run's own data beside its
  steps'), shown as the turn's file chips (`of`), and the change a waiting run asks about (its question's `file`)."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

TOOL: str = "file_change"
RROTOR_MIN: tuple[int, int] = (0, 8)  # the first rrotor whose glyphh_bot gives a bot its folders' files
KEPT: str = "_files"  # in a run's data: [{name, did}], names only
DID: tuple[str, ...] = ("read", "written", "moved")
ACTIONS: tuple[str, ...] = ("write", "move")
KEPT_MAX: int = 200
SHOWN_MAX: int = 12
NAME_MAX: int = 1100
BAD: str = "file_change takes {action: write or move, path, name, to?, to_name?}, each a file's whole path or name."
NO_FOLDERS: str = "{path} is not in a folder {name} may change: give it the folder to read and change, on the bot."


class RunFile(BaseModel):
    name: str = Field(description="The file, as its folder's name and the way down: Invoices/March.pdf")
    did: Literal["read", "written", "moved"] = Field(description="What the run did with it")


def uses(version: str | None) -> bool:
    """Whether a rrotor of this version gives a bot its folders' files."""
    found = re.match(r"(\d+)\.(\d+)", version or "")
    return found is not None and (int(found[1]), int(found[2])) >= RROTOR_MIN


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= NAME_MAX and "\x00" not in value else None


def change(given: Any) -> dict[str, str] | None:
    """A change as the rrotor names it (`{action, path, name, to?, to_name?}`), its strings alone; None for anything
    else."""
    found = given if isinstance(given, dict) else {}
    kept = {k: _text(found.get(k)) for k in ("path", "name")}
    more = {k: _text(found.get(k)) for k in ("to", "to_name") if found.get(k) is not None}
    if found.get("action") not in ACTIONS or None in kept.values() or None in more.values():
        return None
    if (found["action"] == "move") != (set(more) == {"to", "to_name"}):
        return None
    return {"action": found["action"], **kept, **more}  # type: ignore[dict-item]


def may_change(folders: list[dict[str, str]], asked: dict[str, str]) -> str | None:
    """None when every path of the change lies in a folder the bot may change (the most particular folder that
    holds it decides); else the path that does not."""
    for path in (asked["path"], asked.get("to")):
        if path is None:
            continue
        holds = [f for f in folders if path.startswith(f["path"].rstrip("/") + "/")]
        inner = max(holds, key=lambda f: len(f["path"]), default=None)
        if inner is None or inner["access"] != "write" or ".." in path.split("/"):
            return path
    return None


def named(given: Any) -> list[dict[str, str]] | None:
    """The files a rrotor's result names (`data.files`), each `{name, did}` and nothing else; None when the result
    names none at all (a run without its folders' files)."""
    if not isinstance(given, list):
        return None
    kept = [
        {"name": f["name"], "did": f["did"]}
        for f in given
        if isinstance(f, dict) and _text(f.get("name")) and f.get("did") in DID
    ]
    return kept[-KEPT_MAX:]


def merged(before: Any, now: list[dict[str, str]]) -> list[dict[str, str]]:
    """The run's files so far with a result's: each name and what was done with it once, the latest last."""
    seen = [f for f in named(before) or [] if f not in now]
    return [*seen, *now][-KEPT_MAX:]


def of(run: Any) -> list[RunFile]:
    """The files a run read and changed, for its turn's chips: what it changed first, SHOWN_MAX at most."""
    data = run.data if isinstance(run.data, dict) else {}
    kept = named(data.get(KEPT)) or []
    first = [f for f in kept if f["did"] != "read"] + [f for f in kept if f["did"] == "read"]
    return [RunFile(**f) for f in first[:SHOWN_MAX]]


def used(run: Any, spec: dict[str, Any]) -> bool:
    """Whether the run's agent steps had its folders' files: then what the person typed was put to them."""
    data = run.data if isinstance(run.data, dict) else {}
    steps = [s for s in spec.get("loop") or [] if isinstance(s, dict)]
    return KEPT in data and any("agent" in s for s in steps)
