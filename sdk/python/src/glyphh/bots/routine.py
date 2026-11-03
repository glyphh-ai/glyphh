"""A bot's routine: `glyphh bot run <slug> --routine` on the bot's cron. On a Mac it is a launchd job of the
person's own (~/Library/LaunchAgents/ai.glyphh.bot.<slug>.plist); anywhere else the cron line to add is printed,
nothing installed. Times are the machine's local time."""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from xml.sax.saxutils import escape

from .package import Bot, BotError

#: Each cron field: its name in launchd's StartCalendarInterval, and its range.
FIELDS = (("Minute", 0, 59), ("Hour", 0, 23), ("Day", 1, 31), ("Month", 1, 12), ("Weekday", 0, 7))
MAX_INTERVALS = 500


def _field(text: str, low: int, high: int) -> Optional[List[int]]:
    """A cron field's values; None for `*` (every one)."""
    if text == "*":
        return None
    found = set()
    for part in text.split(","):
        rng, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if rng == "*":
            a, b = low, high
        elif "-" in rng:
            a, b = (int(x) for x in rng.split("-", 1))
        else:
            a = b = int(rng)
        if not (low <= a <= b <= high) or step < 1:
            raise ValueError(part)
        found.update(range(a, b + 1, step))
    return sorted(found)


def calendar(cron: str) -> List[Dict[str, int]]:
    """launchd's StartCalendarInterval entries for a five-field cron (numbers, ranges, lists and steps)."""
    fields = cron.split()
    if len(fields) != 5:
        raise BotError(f'the routine\'s cron "{cron}" is not five fields: minute hour day month weekday')
    try:
        values = [_field(f, low, high) for f, (_, low, high) in zip(fields, FIELDS)]
    except ValueError as e:
        raise BotError(f'the routine\'s cron "{cron}" has a field launchd cannot take: {e}') from None
    named = [[(name, v) for v in vals] for (name, _, _), vals in zip(FIELDS, values) if vals is not None]
    entries = [dict(combo) for combo in itertools.product(*named)]
    if len(entries) > MAX_INTERVALS:
        raise BotError(f'the routine\'s cron "{cron}" fires too often for launchd: {len(entries)} times')
    return entries


def command(slug: str) -> List[str]:
    return [sys.executable, "-m", "glyphh", "bot", "run", slug, "--routine"]


def plist(bot: Bot, label: str, log: Path) -> str:
    cron = bot.spec["routine"]["cron"]
    intervals = "".join(
        "<dict>" + "".join(f"<key>{k}</key><integer>{v}</integer>" for k, v in entry.items()) + "</dict>"
        for entry in calendar(cron)
    ) or "<dict/>"
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    if os.environ.get("GLYPHH_BOTS"):
        env["GLYPHH_BOTS"] = os.environ["GLYPHH_BOTS"]
    env_xml = "".join(f"<key>{k}</key><string>{escape(v)}</string>" for k, v in env.items())
    args = "".join(f"<string>{escape(a)}</string>" for a in command(bot.slug))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>EnvironmentVariables</key><dict>{env_xml}</dict>
  <key>StartCalendarInterval</key><array>{intervals}</array>
  <key>StandardOutPath</key><string>{escape(str(log))}</string>
  <key>StandardErrorPath</key><string>{escape(str(log))}</string>
</dict></plist>
"""


def install(
    bot: Bot,
    *,
    platform: str = sys.platform,
    agents: Optional[Path] = None,
    run: Callable[..., Any] = subprocess.run,
    remove: bool = False,
) -> Dict[str, Any]:
    """Install (or `remove`) the bot's routine: a launchd job on a Mac; elsewhere, the cron line to add."""
    routine = bot.spec.get("routine")
    if not routine:
        raise BotError(f'{bot.slug} has no routine: bot.json needs "routine": {{"cron": "M H * * *"}}')
    cron = routine["cron"]
    log = bot.dir / "routine.log"
    label = f"ai.glyphh.bot.{bot.slug}"
    note = f"bot.json says tz {routine['tz']}: launchd and cron use this machine's time" if routine.get("tz") else None
    if platform != "darwin":
        calendar(cron)
        line = f"{cron} {' '.join(command(bot.slug))} >> {log} 2>&1"
        out: Dict[str, Any] = {"bot": bot.slug, "installed": False, "cron_line": line,
                               "how": "add the line with `crontab -e`" if not remove else "remove the line with `crontab -e`"}
        return {**out, "note": note} if note else out
    path = (agents or Path.home() / "Library" / "LaunchAgents") / f"{label}.plist"
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    if remove:
        path.unlink(missing_ok=True)
        return {"bot": bot.slug, "removed": True, "label": label}
    text = plist(bot, label, log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, check=True)
    out = {"bot": bot.slug, "installed": True, "label": label, "plist": str(path), "cron": cron, "log": str(log),
           "runs": " ".join(command(bot.slug))}
    return {**out, "note": note} if note else out
