"""A bot's know-how as Claude plugins the Agent SDK loads (docs/specs/bot-agent-loop.md, 7): the plugins installed
for it (bot_plugins: a template's package, its files kept at the version installed) and its own notes
(`bots.skills`, name: SKILL.md), written as one more plugin, `notes`, in the same format. Each is written into the
run's folder for the turn; the skills are named `<plugin>:<skill>`, which is all the session may load."""

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import BotPlugin

NOTES: str = "notes"
MANIFEST: str = ".claude-plugin/plugin.json"
SIDECAR: str = "glyphh.json"
SKILL: re.Pattern[str] = re.compile(r"skills/([a-z0-9][a-z0-9-]{0,62})/SKILL\.md")


@dataclass(frozen=True)
class Plugin:
    name: str
    version: str
    source: str  # template:<slug>, or personal
    files: dict[str, str]

    @property
    def skills(self) -> list[str]:
        return [f"{self.name}:{m.group(1)}" for path in sorted(self.files) if (m := SKILL.fullmatch(path))]

    @property
    def code(self) -> list[dict[str, Any]]:
        """The skills that carry code, as its sidecar declares them: [{skill, scripts}]; code runs only on a rrotor."""
        side = json.loads(self.files.get(SIDECAR) or "{}")
        return [{"skill": c["skill"], "scripts": list(c["scripts"])} for c in side.get("code") or []]

    @property
    def scripts(self) -> list[str]:
        return [s for c in self.code for s in c["scripts"]]


def notes(bot: Any) -> Plugin | None:
    """The bot's own notes as a plugin; None when it has none."""
    if not bot.skills:
        return None
    about = {"name": NOTES, "version": "1.0.0", "description": f"{bot.name}'s own notes"}
    files = {MANIFEST: json.dumps(about)} | {f"skills/{name}/SKILL.md": said for name, said in bot.skills.items()}
    return Plugin(NOTES, "1.0.0", "personal", files)


async def of(conn: AsyncConnection, bot: Any) -> list[Plugin]:
    """The bot's plugins: those installed for it, by name, then its own notes."""
    rows = await conn.execute(select(BotPlugin).where(BotPlugin.bot_id == bot.id).order_by(BotPlugin.name))
    found = [Plugin(r.name, r.version, r.source, dict(r.files)) for r in rows]
    own = notes(bot)
    return [*found, own] if own is not None else found


def _safe(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path) and not p.is_absolute() and ".." not in p.parts


def written(folder: Path, plugins: list[Plugin]) -> list[Path]:
    """Each plugin written under `folder`/plugins; where each is."""
    made = []
    for plugin in plugins:
        root = folder / "plugins" / plugin.name
        for path, said in plugin.files.items():
            if _safe(path):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(said, "utf-8")
        made.append(root)
    return made
