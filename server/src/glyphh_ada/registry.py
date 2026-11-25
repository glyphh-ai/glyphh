"""Ada versions (docs/specs/ada-cloud.md, 12): the names customers see (`ada-1-0`, `ada-1-1-beta`), each one release
of the kernel, from ada_versions.json. The API and the workers both read it; it never imports the kernel.

A version's status comes from its dates: stable or beta; deprecated from `deprecated` (it answers, but cannot be
chosen); retired from `ends` (its models are moved to the latest stable). The latest stable is the newest stable that
is neither. The list is checked when it is read: the support policy's bounds hold or the server does not start."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from glyphh_ada.errors import Refusal

FILE: Path = Path(__file__).with_name("ada_versions.json")
NAME: re.Pattern[str] = re.compile(r"^ada-\d+-\d+(-beta)?$")
KEPT_MAX: int = 3  # the latest stable, the stable before it while deprecated, one beta
MOVED_BY: str = "ada-retirement"  # who a move off a retired version is made by
MOVED_DAYS: int = 30  # a model says it was moved for this long
CONTRACT: int = 5  # the contract (glyphh-ai/glyphh contract/contract.json) the Ada API speaks


@dataclass(frozen=True)
class Version:
    name: str
    kernel: str
    commit: str
    beta: bool
    open: bool
    released: date
    deprecated: date | None
    ends: date | None
    changes_answers: bool
    store_format: int
    aliases: tuple[str, ...]
    summary: str
    notes: str
    installed: bool = True

    def status(self, today: date) -> str:
        if self.ends is not None and today >= self.ends:
            return "retired"
        if self.deprecated is not None and today >= self.deprecated:
            return "deprecated"
        return "beta" if self.beta else "stable"


def _day(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _version(raw: dict[str, Any]) -> Version:
    return Version(
        name=raw["name"],
        kernel=raw["kernel"],
        commit=raw["commit"],
        beta=raw["status"] == "beta",
        open=bool(raw.get("open", True)),
        released=date.fromisoformat(raw["released"]),
        deprecated=_day(raw.get("deprecated")),
        ends=_day(raw.get("ends")),
        changes_answers=bool(raw["changes_answers"]),
        store_format=int(raw["store_format"]),
        aliases=tuple(raw.get("aliases", ())),
        summary=raw["summary"],
        notes=raw["notes"],
        installed=bool(raw.get("installed", True)),
    )


class Registry:
    def __init__(self, versions: list[Version]) -> None:
        self.versions = versions  # newest first
        self._by = {v.name: v for v in versions} | {a: v for v in versions for a in v.aliases}
        check(self)

    def find(self, name: str) -> Version | None:
        return self._by.get(name)

    def latest(self, today: date) -> Version:
        """The latest stable: the newest stable neither deprecated nor retired."""
        return next(v for v in self.versions if v.status(today) == "stable")

    def kernels(self) -> list[str]:
        """Every kernel this deploy runs, one each, newest first."""
        return list(dict.fromkeys(v.kernel for v in self.versions if v.installed))

    def kernel_of(self, name: str) -> str:
        """The kernel a model pinned to this name runs on ('' when the name is unknown)."""
        found = self.find(name)
        return found.kernel if found else ""

    def choose(self, name: str | None, today: date) -> Version:
        """The version a new model or an upgrade goes to: the latest stable when none is named; a named one only when
        it may be chosen (never substituted: an unknown, retired, deprecated or closed one is refused, naming the
        latest stable as the fix)."""
        latest = self.latest(today)
        if name is None:
            return latest
        found = self.find(name)
        fix = {"ada": name, "latest": latest.name}
        if found is None:
            raise Refusal(
                "E_ADA_UNKNOWN", f"There is no Ada version {name}: the latest stable is {latest.name}.", 422, **fix
            )
        status = found.status(today)
        if status == "retired":
            message = f"{name} was retired on {found.ends}: the latest stable is {latest.name}."
            raise Refusal("E_ADA_RETIRED", message, 410, **fix)
        if status == "deprecated":
            message = f"{name} is deprecated (it ends on {found.ends}) and cannot be chosen: use {latest.name}."
            raise Refusal("E_ADA_DEPRECATED", message, 422, **fix, ends=str(found.ends))
        if not found.open:
            message = f"The beta {name} is closed to new models: use {latest.name}."
            raise Refusal("E_ADA_BETA", message, 422, **fix)
        if not found.installed:
            raise Refusal("E_ADA_UNAVAILABLE", f"{name} is not running here: use {latest.name}.", 503, **fix)
        return found

    def view(self, v: Version, today: date) -> dict[str, Any]:
        return {
            "name": v.name,
            "kernel": v.kernel,
            "status": v.status(today),
            "beta": v.beta,
            "open": v.open,
            "released": str(v.released),
            "deprecated": None if v.deprecated is None else str(v.deprecated),
            "ends": None if v.ends is None else str(v.ends),
            "changes_answers": v.changes_answers,
            "aliases": list(v.aliases),
            "summary": v.summary,
            "notes": v.notes,
        }

    def notice(self, name: str, made_by: str, made_at: datetime | None, today: date) -> dict[str, Any] | None:
        """What a model running this version should be told: it was moved off a retired one, its version is
        deprecated or retired, a newer stable is out, or a newer beta may be tried. None when nothing."""
        found, latest = self.find(name), self.latest(today)
        if found is None:
            return None
        status = found.status(today)
        if made_by == MOVED_BY and made_at is not None and made_at.date() > today - timedelta(days=MOVED_DAYS):
            return {"kind": "moved", "message": f"Moved to {name} on {made_at.date()}: its Ada version was retired."}
        if status == "retired":
            return {
                "kind": "retired",
                "message": f"{name} was retired on {found.ends}: this model is being moved to {latest.name}.",
                "to": latest.name,
                "ends": str(found.ends),
            }
        if status == "deprecated":
            return {
                "kind": "deprecated",
                "message": f"{name} is deprecated and ends on {found.ends}: upgrade to {latest.name}.",
                "to": latest.name,
                "ends": str(found.ends),
            }
        newer = self.versions[: self.versions.index(found)]
        if latest in newer:
            return {"kind": "upgrade", "message": f"{latest.name} is available: see what changes.", "to": latest.name}
        beta = next((v for v in newer if v.beta and v.open and v.status(today) == "beta"), None)
        if beta is not None:
            return {"kind": "beta", "message": f"{beta.name} is available to try (beta).", "to": beta.name}
        return None


def check(reg: Registry) -> None:
    """The support policy's bounds (docs/specs/ada-cloud.md, 12.5); a list that breaks one is refused at start."""
    names = [v.name for v in reg.versions] + [a for v in reg.versions for a in v.aliases]
    problems = [f"{n}: not a name like ada-1-0 or ada-1-1-beta" for n in names if not NAME.match(n)]
    problems += [f"{n}: named twice" for n in sorted({n for n in names if names.count(n) > 1})]
    problems += [f"{v.name}: a beta's name ends -beta" for v in reg.versions if v.beta != v.name.endswith("-beta")]
    problems += [f"{v.name}: deprecated without an end" for v in reg.versions if v.deprecated and v.ends is None]
    installed = [v for v in reg.versions if v.installed]
    if len({v.kernel for v in installed}) > KEPT_MAX:
        problems.append(f"more than {KEPT_MAX} kernels installed")
    if len({v.store_format for v in installed}) > 1:
        problems.append("the installed kernels read different store formats")
    if not any(not v.beta and v.deprecated is None for v in reg.versions):
        problems.append("no stable version that is not deprecated")
    if problems:
        raise ValueError("ada_versions.json: " + "; ".join(problems))


def load(path: Path = FILE) -> Registry:
    return Registry([_version(raw) for raw in json.loads(path.read_text())["versions"]])


@cache
def registry() -> Registry:
    return load()


def today() -> date:
    return datetime.now(UTC).date()
