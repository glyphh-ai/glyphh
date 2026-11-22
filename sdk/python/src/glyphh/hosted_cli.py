"""`glyphh bots ...`: the org's hosted bots (the ones Glyphh runs: glyphh.hosted) from a terminal, on the same API key
as the rest of the glyphh command. Every answer is the API's own JSON on stdout. (`glyphh bot ...` is the bots on this
machine.)

    glyphh bots list [--q words]          glyphh bots run inbox-cat --input "lunch?" --wait
    glyphh bots approvals                 glyphh bots answer <run id> yes --wait
    glyphh bots templates                 glyphh bots install news-brief"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from .hosted import HostedBots

Out = Callable[[Any], None]


def _answer(text: str) -> Any:
    """An answer as given: one of the options, `N=option ...` for a batch, or a JSON map."""
    if text.lstrip().startswith("{"):
        return json.loads(text)
    return text


def _stopped(a: argparse.Namespace, run: Any) -> Any:
    if getattr(run, "status", None) == "failed":
        a.exit_code = 1
    return run


def register(sub: Any, out: Out) -> None:
    """The `bots` command and its own commands, on the glyphh command's subparsers."""

    def client() -> HostedBots:
        return HostedBots()

    top = sub.add_parser("bots", help="Your org's hosted bots: list, run, answer, cancel, correct, install a template",
                         description="The bots Glyphh hosts for your org (the Glyphh API, GLYPHH_API_URL): JSON on stdout.")
    cmds = top.add_subparsers(dest="bots_command", required=True, metavar="command")

    def cmd(name: str, about: str, run: Callable[[argparse.Namespace, HostedBots], Any]) -> argparse.ArgumentParser:
        p = cmds.add_parser(name, help=about, description=about)
        p.set_defaults(run=lambda a: out(run(a, client())))
        return p

    def waits(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--wait", action="store_true", help="wait until it ends or asks the person")
        p.add_argument("--timeout", type=float, default=1800.0, help="seconds to wait (default 1800)")
        return p

    p = cmd("list", "The org's bots; --q finds those with every word", lambda a, b: b.list(a.q))
    p.add_argument("--q", help="words its name, slug or summary has")
    p = cmd("get", "One bot: its loop, gates, connections, schedule, last run", lambda a, b: b.get(a.slug))
    p.add_argument("slug")
    p = cmd("gates", "What a bot's gates have learned", lambda a, b: b.gates(a.slug))
    p.add_argument("slug")
    p = waits(cmd("run", "Run a bot on an input, in the background",
                  lambda a, b: _stopped(a, b.run(a.slug, a.input, wait=a.wait, timeout=a.timeout))))
    p.add_argument("slug")
    p.add_argument("--input", default="", help="what the bot is given to work on ($input)")
    p = cmd("runs", "A bot's runs, the newest first", lambda a, b: b.runs(a.slug))
    p.add_argument("slug")
    p = cmd("status", "One run: its status, output, question; --wait waits for it",
            lambda a, b: _stopped(a, b.wait(a.id, timeout=a.timeout) if a.wait else b.get_run(a.id)))
    waits(p).add_argument("id", help="the run's id")
    p = waits(cmd("answer", "Answer the run that waits on the person",
                  lambda a, b: _stopped(a, b.answer(a.id, a.answer, wait=a.wait, timeout=a.timeout))))
    p.add_argument("id", help="the run's id")
    p.add_argument("answer", type=_answer, help="one of its options (yes, no, ...); a batch: '1=answer rest=skip' or JSON")
    p = cmd("cancel", "End the run that waits on the person", lambda a, b: b.cancel(a.id))
    p.add_argument("id", help="the run's id")
    p = cmd("wrong", "A gate called the run wrong: what it should have said, learned",
            lambda a, b: b.wrong(a.id, a.outcome, gate=a.gate, item=a.item))
    p.add_argument("id", help="the run's id")
    p.add_argument("outcome", help="what the gate should have said")
    p.add_argument("--gate", help="which gate, when the run passed more than one")
    p.add_argument("--item", help="which item, for a gate over many: its key")
    cmd("approvals", "Every run waiting on the person, oldest first", lambda a, b: b.approvals())
    p = cmd("templates", "The bot templates Glyphh ships", lambda a, b: b.templates(a.q))
    p.add_argument("--q", help="words its name has")
    p = cmd("template", "One template: what it does, the apps it needs", lambda a, b: b.template(a.slug))
    p.add_argument("slug")
    p = cmd("install", "Copy a template into the org as its own bot", lambda a, b: b.install(a.slug, name=a.name))
    p.add_argument("slug")
    p.add_argument("--name", help="its name in the org (default: the template's)")
