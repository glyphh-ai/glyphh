"""Two parts of a bot template's package (ops/bots/packages.py) read and checked: its skills (skills/<name>/SKILL.md)
and its program (program.py, docs/specs/programs.md): the program's steps, read without running the file, each
problem said. A program with a code step runs on a rrotor, so its package does too."""

import re
from typing import Any

from glyphh_server.ops.programs import flow

IN_SKILL: re.Pattern[str] = re.compile(r"skills/([^/]+)/(.+)")
FRONT: re.Pattern[str] = re.compile(r"\A---\n(.*?)\n---(\n|\Z)", re.S)
PROGRAM: str = "program.py"


def skills(texts: dict[str, str], problems: list[str]) -> list[str]:
    """The package's skills by name: each folder under skills/ holds a SKILL.md whose frontmatter names it."""
    names = sorted({m.group(1) for p in texts if (m := IN_SKILL.fullmatch(p))})
    for name in names:
        path = f"skills/{name}/SKILL.md"
        if path not in texts:
            problems.append(f"The skill {name} has no SKILL.md.")
            continue
        front = FRONT.match(texts[path])
        said = dict(re.findall(r"^([\w-]+):[ \t]*(\S.*)$", front.group(1) if front else "", re.M))
        if not said.get("name") or not said.get("description"):
            problems.append(f"{path} needs a name and a description in its frontmatter.")
        elif said["name"].strip() != name:
            problems.append(f"{path} names itself {said['name'].strip()}: a skill is named as its folder, {name}.")
    return names


def program(texts: dict[str, str], problems: list[str]) -> list[dict[str, Any]]:
    """The steps of the package's program.py (none without one)."""
    if PROGRAM not in texts:
        return []
    try:
        steps, functions = flow.read(texts[PROGRAM])
    except flow.Bad as err:
        problems.append(str(err))
        return []
    problems += [f"{PROGRAM}: {p}" for p in flow.check(steps, functions)]
    return steps


def has_code(steps: list[dict[str, Any]]) -> bool:
    return any(s.get("kind") == "code" for s in steps)
