"""A bot as the SDK runs it (glyphh.bots): its package written into a folder (bot.json, agent.md, skills/), loaded and
checked by the SDK, every problem said at once, and the runner's state (its runs.sqlite) carried in the bot's row
between runs. The cloud gives a bot no code of its own: its program is the cloud's (ops/bots/cloud.py)."""

import json
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from glyphh.bots import Bot as Package
from glyphh.bots import BotError

from glyphh_server.errors import Invalid

SKILL_NAME: re.Pattern[str] = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
OURS: tuple[str, ...] = ("slug", "name", "summary", "agent")  # the server's, from the bot's own fields
STATE: str = "runs.sqlite"
SLUG_MAX: int = 30  # its Ada models are named bot-<slug>-gate-<gate>, at most 63 characters
NO_FUNCTION: re.Pattern[str] = re.compile(r"step (\S+): program\.py has no function (\S+)")


def loop_slug(slug: str) -> str:
    """The SDK's slug for the bot: snake_case, as its Ada models are named by it (bot-<slug>-gate-<gate>)."""
    return slug.replace("-", "_")


def gate_models(slug: str, spec: dict[str, Any]) -> list[str]:
    from glyphh.bots import KINDS, model_name

    s = loop_slug(slug)
    gates = spec.get("gates") if isinstance(spec.get("gates"), dict) else {}
    return [model_name("bot", s, "gate", g) for g in gates] + [model_name("bot", s, k) for k in KINDS]


def write(folder: Path, bot: Any) -> Path:
    """The bot's package in `folder` (made), its state too when it has one."""
    folder.mkdir(parents=True, exist_ok=True)
    spec = {k: v for k, v in bot.spec.items() if k not in OURS}
    full = {**spec, "slug": loop_slug(bot.slug), "name": bot.name, "summary": bot.summary, "agent": "agent.md"}
    (folder / "bot.json").write_text(json.dumps(full), "utf-8")
    about = " ".join(bot.summary.split()) or bot.name
    (folder / "agent.md").write_text(
        f"---\nname: {loop_slug(bot.slug)}\ndescription: {about}\n---\n\n{bot.instructions}\n", "utf-8"
    )
    for name, text in bot.skills.items():
        if not SKILL_NAME.fullmatch(name):
            raise Invalid(f"A skill's name is lower case letters, digits and -: {name!r} is not.", reason="skills")
        skill = folder / "skills" / name
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(text, "utf-8")
    if bot.state:
        (folder / STATE).write_bytes(bot.state)
    return folder


def _plain(problem: str) -> str:
    """The SDK's words for a run step's missing function, said as the cloud has it: a tool the bot may not use."""
    m = NO_FUNCTION.fullmatch(problem)
    if m is None:
        return problem
    return f"step {m.group(1)}: {m.group(2)} is neither fetch nor a tool the bot may use (scope it on a connection)"


def load(folder: Path, program: Any) -> Package:
    try:
        return Package.load(folder, program=program)
    except BotError as err:
        problems = [_plain(p) for p in err.problems] or [err.message]
        raise Invalid(f"The bot is not right: {problems[0]}", reason="spec", problems=problems) from err


@contextmanager
def opened(bot: Any, program: Any) -> Iterator[Package]:
    """The bot's package in a folder of its own for as long as it is open (the runner's state in it)."""
    with tempfile.TemporaryDirectory(prefix="glyphh-bot-") as d:
        yield load(write(Path(d) / loop_slug(bot.slug), bot), program)


def check(bot: Any, program: Any) -> None:
    """The bot as given is one the SDK runs, or Invalid says every problem (`problems`)."""
    with opened(bot, program):
        pass


def state(folder: Path) -> bytes | None:
    found = folder / STATE
    return found.read_bytes() if found.exists() else None
