"""A bot as the SDK's runner opens it (glyphh.bots): its package written into a folder (bot.json, agent.md), loaded
and checked by the SDK, every problem said at once, and the runner's state (its runs.sqlite: the decisions, what
they learned from, their probes' references) carried in the bot's row between goes. The runner no longer walks a
bot's loop (a run is the Agent SDK's, ops/bots/agent): the package's loop is one step per decision, which is what
the SDK needs to hold the decisions' Ada models and policies."""

import json
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from glyphh.bots import Bot as Package
from glyphh.bots import BotError

from glyphh_server.errors import Invalid

SKILL_NAME: re.Pattern[str] = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
KEPT: tuple[str, ...] = ("gates", "seed", "hosts", "reads_glyphh")  # of a bot's spec, what the SDK reads
STATE: str = "runs.sqlite"
SLUG_MAX: int = 30  # its Ada models are named bot-<slug>-gate-<gate>, at most 63 characters
ANSWER: list[dict[str, Any]] = [{"id": "answer", "agent": "Answer the person."}]


def loop_slug(slug: str) -> str:
    """The SDK's slug for the bot: snake_case, as its Ada models are named by it (bot-<slug>-gate-<gate>)."""
    return slug.replace("-", "_")


def gate_models(slug: str, spec: dict[str, Any]) -> list[str]:
    from glyphh.bots import KINDS, model_name

    s = loop_slug(slug)
    gates = spec.get("gates") if isinstance(spec.get("gates"), dict) else {}
    return [model_name("bot", s, "gate", g) for g in gates] + [model_name("bot", s, k) for k in KINDS]


def skills(given: dict[str, str]) -> None:
    """A bot's notes are named as skills are; Invalid says which is not."""
    for name in given:
        if not SKILL_NAME.fullmatch(name):
            raise Invalid(f"A note's name is lower case letters, digits and -: {name!r} is not.", reason="skills")


def write(folder: Path, bot: Any) -> Path:
    """The bot's package in `folder` (made), its state too when it has one."""
    folder.mkdir(parents=True, exist_ok=True)
    spec = {k: v for k, v in bot.spec.items() if k in KEPT}
    gates = spec.get("gates") if isinstance(spec.get("gates"), dict) else {}
    loop = [{"id": name, "gate": name, "each": "$input"} for name in gates] or ANSWER
    full = {**spec, "loop": loop, "slug": loop_slug(bot.slug), "name": bot.name, "summary": bot.summary}
    (folder / "bot.json").write_text(json.dumps({**full, "agent": "agent.md"}), "utf-8")
    about = " ".join(bot.summary.split()) or bot.name
    (folder / "agent.md").write_text(
        f"---\nname: {loop_slug(bot.slug)}\ndescription: {about}\n---\n\n{bot.instructions}\n", "utf-8"
    )
    if bot.state:
        (folder / STATE).write_bytes(bot.state)
    return folder


def load(folder: Path) -> Package:
    try:
        return Package.load(folder, program=SimpleNamespace())  # no code of its own: its decisions alone
    except BotError as err:
        problems = list(err.problems) or [err.message]
        raise Invalid(f"The bot is not right: {problems[0]}", reason="spec", problems=problems) from err


@contextmanager
def opened(bot: Any) -> Iterator[Package]:
    """The bot's package in a folder of its own for as long as it is open (the runner's state in it)."""
    with tempfile.TemporaryDirectory(prefix="glyphh-bot-") as d:
        yield load(write(Path(d) / loop_slug(bot.slug), bot))


def check(bot: Any) -> None:
    """The bot as given is one the SDK holds, or Invalid says every problem (`problems`)."""
    skills(bot.skills)
    with opened(bot):
        pass


def state(folder: Path) -> bytes | None:
    found = folder / STATE
    return found.read_bytes() if found.exists() else None
