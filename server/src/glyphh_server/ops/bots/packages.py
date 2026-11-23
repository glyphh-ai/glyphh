"""A bot template is a Claude plugin package (docs/specs/bot-agent-loop.md, 7): a folder under library/ with the
standard manifest (.claude-plugin/plugin.json), the bot's know-how as skills (skills/<name>/SKILL.md) and Glyphh's
sidecar (glyphh.json): the bot it makes, the apps and tools it requires, what Ada decides, its standing task and its
examples; and, beside it, a program (program.py: docs/specs/programs.md) installed with the bot. `check` says
everything wrong with a package at once; `library` is the packages Glyphh ships."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PositiveInt, ValidationError

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import package_parts as parts

LIBRARY: Path = Path(__file__).with_name("library")
MANIFEST: str = ".claude-plugin/plugin.json"
SIDECAR: str = "glyphh.json"
SKIPPED: frozenset[str] = frozenset(("seeds", "__pycache__", ".DS_Store"))
NAME: re.Pattern[str] = re.compile(r"[a-z][a-z0-9-]{0,30}")
VERSION: re.Pattern[str] = re.compile(r"\d+\.\d+\.\d+")
MAX_BYTES: int = 1_000_000


class BotCard(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(description="A few plain words on what it does")
    description: str
    look: dict[str, str] = Field(default_factory=dict)
    instructions: str = Field(min_length=1)
    model: str = Field(min_length=1)
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"


class Requires(BaseModel, extra="forbid"):
    app: str = Field(min_length=1, description="A Pipedream app slug")
    tools: list[str] = Field(default_factory=list, description="The app's tools it uses, by key (<app>-<action>)")


class Code(BaseModel, extra="forbid"):
    skill: str
    scripts: list[str]
    why: str


class Sidecar(BaseModel, extra="forbid"):
    bot: BotCard
    requires: list[Requires] = Field(default_factory=list)
    decisions: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="The decisions the bot can ask Ada about"
    )
    hosts: list[str] = Field(default_factory=list)
    builtins: list[str] = Field(default_factory=list)
    task: str = Field(min_length=1, description="What it does when it runs on its own")
    schedule: dict[str, Any] = Field(default_factory=dict)
    examples: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=6)
    connector_tools: list[dict[str, Any]] = Field(default_factory=list)
    limits: dict[Literal["turns", "seconds", "tokens", "runs_per_day"], PositiveInt] = Field(default_factory=dict)
    code: list[Code] = Field(default_factory=list)
    folders: bool = False
    runs_on: list[str] | None = Field(None, description="Where it can run; derived when left out")


@dataclass(frozen=True)
class Package:
    slug: str
    version: str
    description: str
    sidecar: Sidecar
    files: dict[str, str]
    skills: list[str]
    runs_on: list[str]


def runs_on(sidecar: Sidecar, steps: list[dict[str, Any]] | None = None) -> list[str]:
    """Where a package can run: one with code (its skills' scripts, its program's code steps) or folders needs a
    sandbox, so a rrotor only; any other, anywhere."""
    sandboxed = sidecar.code or sidecar.folders or parts.has_code(steps or [])
    return ["rrotor"] if sandboxed else ["cloud", "rrotor"]


def _texts(files: Mapping[str, str | bytes], problems: list[str]) -> dict[str, str]:
    """Each file as text, by its path; a bad path, a file that is not text and too large a package are problems."""
    out: dict[str, str] = {}
    size = 0
    for path, body in files.items():
        raw = body.encode() if isinstance(body, str) else body
        size += len(raw)
        if path.startswith(("/", "\\")) or ".." in path.split("/"):
            problems.append(f"{path} is not a path inside the package: no leading / and no '..'.")
            continue
        try:
            out[path] = raw.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{path} is not UTF-8 text: a package holds text files only.")
    if size > MAX_BYTES:
        problems.append(f"The package is {size:,} bytes: the most is {MAX_BYTES:,}.")
    return out


def _json(texts: dict[str, str], path: str, problems: list[str]) -> dict[str, Any] | None:
    """The JSON object a file holds; None, with the problem said, when it is missing or is not one."""
    try:
        found = json.loads(texts[path]) if path in texts else None
    except ValueError:
        found = None
    if isinstance(found, dict):
        return found
    problems.append(f"{path} is not a JSON object." if path in texts else f"{path} is missing.")
    return None


def _manifest(texts: dict[str, str], problems: list[str]) -> dict[str, Any]:
    found = _json(texts, MANIFEST, problems)
    if found is None:
        return {}
    if not (isinstance(found.get("name"), str) and NAME.fullmatch(found["name"])):
        problems.append(f"{MANIFEST} needs a name: a lowercase letter, then up to 30 lowercase letters, digits or -.")
    if not (isinstance(found.get("version"), str) and VERSION.fullmatch(found["version"])):
        problems.append(f"{MANIFEST} needs a version of three numbers, like 1.0.0.")
    return found


def _sidecar(texts: dict[str, str], problems: list[str]) -> Sidecar | None:
    found = _json(texts, SIDECAR, problems)
    try:
        return None if found is None else Sidecar.model_validate(found)
    except ValidationError as e:
        for err in e.errors():
            where = ".".join(str(part) for part in err["loc"])
            said = f"{SIDECAR}, {where}: {err['msg']}."
            problems.append(f"{SIDECAR} has an unknown key: {where}." if err["type"] == "extra_forbidden" else said)
        return None


def _fits(sidecar: Sidecar, skills: list[str], texts: dict[str, str], steps: list[dict[str, Any]]) -> list[str]:
    """What a well-formed sidecar still gets wrong, each in a sentence."""
    out = [
        f"The tool {key} is not one of {r.app}'s: its key starts with {r.app}-."
        for r in sidecar.requires for key in r.tools if not key.startswith(f"{r.app}-")
    ]  # fmt: skip
    for name, d in sidecar.decisions.items():
        if not isinstance(d.get("outcomes"), list) or len(d["outcomes"]) < 2:
            out.append(f"The decision {name} needs at least two outcomes.")
        if not isinstance(d.get("case"), dict) or not d["case"]:
            out.append(f"The decision {name} needs a case: how an item becomes what Ada reads.")
    for c in sidecar.code:
        if c.skill not in skills:
            out.append(f"The code names the skill {c.skill}, which is not in the package.")
        out += [f"The code names the script {s}, which is not in the package." for s in c.scripts if s not in texts]
    if sidecar.runs_on is not None and sidecar.runs_on != (fit := runs_on(sidecar, steps)):
        out.append(f"runs_on must be {json.dumps(fit)}: code and folders need a rrotor, anything else runs anywhere.")
    return out


def check(files: Mapping[str, str | bytes]) -> Package:
    """The package these files make (each by its path, as text or bytes); refused, saying every problem at once."""
    problems: list[str] = []
    texts = _texts(files, problems)
    manifest = _manifest(texts, problems)
    skills = parts.skills(texts, problems)
    steps = parts.program(texts, problems)
    sidecar = _sidecar(texts, problems)
    if sidecar is not None:
        problems += _fits(sidecar, skills, texts, steps)
    if problems or sidecar is None:
        raise Invalid(f"The package does not fit: {len(problems)} to fix.", reason="package", problems=problems)
    return Package(
        slug=manifest["name"], version=manifest["version"], description=str(manifest.get("description") or ""),
        sidecar=sidecar, files=texts, skills=skills, runs_on=runs_on(sidecar, steps),
    )  # fmt: skip


def read(folder: Path) -> dict[str, bytes]:
    """Every file of a package's folder, by its path from the folder."""
    found = (p for p in sorted(folder.rglob("*")) if p.is_file() and not SKIPPED & set(p.relative_to(folder).parts))
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in found}


@cache
def library() -> dict[str, Package]:
    """The packages Glyphh ships, by slug: every folder of library/ but the seeds."""
    made = [check(read(d)) for d in sorted(LIBRARY.iterdir()) if d.is_dir() and d.name not in SKIPPED]
    return {p.slug: p for p in made}
