"""`glyphh bot ...`: bots from a terminal. Every answer is JSON on stdout, as the rest of the glyphh command; what a
run does as it goes, and the questions a gate or an approval asks, are on stderr. A question at the terminal is
answered there; in a routine (or with no terminal) it stops the run, `needs_input`, until `glyphh bot continue`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from .claude import Claude
from .orchestrator import KEEP, TRUST, Orchestrator, connect
from .package import TOUCHES, Bot, BotError, bots_root
from .routine import install as install_routine

Out = Callable[[Any], None]


def _terminal_ask(question: str, options: List[str]) -> str:
    sys.stderr.write(f"\n? {question} [{'/'.join(options)}] ")
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        raise BotError("no answer: the terminal closed")
    return line


def _echo(quiet: bool) -> Optional[Callable[[str], None]]:
    if quiet:
        return None
    return lambda line: print(f"  {line}", file=sys.stderr)


def orchestrator(a: argparse.Namespace) -> Orchestrator:
    """The orchestrator for a command: questions asked at the terminal when there is one and no routine runs."""
    root = bots_root()
    ask = _terminal_ask if not getattr(a, "routine", False) and sys.stdin.isatty() else None
    return Orchestrator(connect(root), root=root, claude=Claude(), ask=ask, echo=_echo(getattr(a, "quiet", False)))


def register(sub: Any, out: Out) -> None:
    """The `bot` command and its own commands, on the glyphh command's subparsers."""
    top = sub.add_parser("bot", help="Bots: make one from a job, run it, answer it, correct it, trust and keep it",
                         description="Bots in ~/.glyphh/bots (GLYPHH_BOTS): every answer is JSON on stdout.")
    bots = top.add_subparsers(dest="bot_command", required=True, metavar="command")

    def cmd(name: str, about: str, run: Callable[[argparse.Namespace], Any]) -> argparse.ArgumentParser:
        p = bots.add_parser(name, help=about, description=about)
        p.add_argument("--quiet", "-q", action="store_true", help="nothing on stderr as it goes")

        def go(a: argparse.Namespace) -> None:
            got = run(a)
            out(got.to_dict() if hasattr(got, "to_dict") else got)
            if getattr(got, "status", None) == "failed":
                a.exit_code = 1

        p.set_defaults(run=go)
        return p

    cmd("init", "Make the orchestrator's memory and gates in Ada (once; install and new do it too)",
        lambda a: orchestrator(a).ensure())
    p = cmd("check", "Check a bot's package folder without installing it", _check)
    p.add_argument("folder")
    p = cmd("install", "Install a bot from its package folder: its gate and memory models, its seed", _install)
    p.add_argument("source", help="the bot's folder (or the slug of one already in the bots' home)")
    p.add_argument("--job", help="the job it does, as the orchestrator keeps it (default: its summary)")
    p = cmd("new", "Make a bot from a job: make_bot decides, the builder writes it, it is checked and installed", _new)
    p.add_argument("job", help="the job, in a sentence")
    p.add_argument("--recurs", type=int, default=7, help="how many times a week the job comes up (default 7)")
    p.add_argument("--touches", choices=TOUCHES, default="read_only", help="the most outward thing it may do")
    p.add_argument("--answer", choices=["make", "not_yet", "no"], help="your make_bot call, when Ada asks")
    p = cmd("run", "One run of a bot's loop", lambda a: orchestrator(a).runner(a.slug).run(routine=a.routine))
    p.add_argument("slug")
    p.add_argument("--routine", action="store_true", help="nobody watching: a question stops the run")
    p = cmd("continue", "Carry on the bot's run that waits, with the answer to its question (or its batch's answers)",
            lambda a: orchestrator(a).runner(a.slug).resume(_answer(a.answer)))
    p.add_argument("slug")
    p.add_argument("answer", nargs="*",
                   help="one of the question's options; for a batch of items N=outcome for each (1=read 2=skip, "
                        "rest=skip) or a JSON map; asked here when left out")
    p = cmd("wrong", "A gate decided a run (or one item of it) wrong: record what it should have been",
            lambda a: orchestrator(a).runner(a.slug).wrong(a.run_id, a.outcome, a.gate, a.item))
    p.add_argument("slug")
    p.add_argument("run_id", metavar="run", help="the run's id, or last")
    p.add_argument("outcome")
    p.add_argument("--gate", help="which gate, when the run passed several")
    p.add_argument("--item", help="which item of a per-item gate: its number in the run, or its key")
    p = cmd("outcome", "What really happened to a case a gate decided (a world-answered gate): kept as a precedent",
            _outcome)
    p.add_argument("slug")
    p.add_argument("run_id", metavar="run", help="the run's id, or last")
    p.add_argument("gate")
    p.add_argument("rest", nargs="+", metavar="[item] outcome", help="the item (its number or key) when the gate "
                   "decided several, then the outcome")
    p = cmd("pause", "The kill switch: the bot refuses to run, its routine included, until resume",
            lambda a: orchestrator(a).runner(a.slug).pause(a.why or ""))
    p.add_argument("slug")
    p.add_argument("--why", help="why, kept with the pause")
    p = cmd("resume", "Let a paused bot run again", lambda a: orchestrator(a).runner(a.slug).unpause())
    p.add_argument("slug")
    p = cmd("gates", "Each gate's record: precedents, Ada's calls and the person's, ask rate, audits, overrules",
            lambda a: orchestrator(a).runner(a.slug).gates(a.runs))
    p.add_argument("slug")
    p.add_argument("--runs", type=int, default=10, help="the last N runs the ask rate is read over (default 10)")
    p = cmd("report", "Write the bot's report.html (its last run's decisions, the ask rate run by run, its gates)",
            lambda a: orchestrator(a).runner(a.slug).report(a.runs))
    p.add_argument("slug")
    p.add_argument("--runs", type=int, default=30, help="the last N runs it shows (default 30)")
    p = cmd("status", "The orchestrator and every bot; with a slug, that bot's gates, memory and last runs", _status)
    p.add_argument("slug", nargs="?")
    p = cmd("review", "trust_bot and keep_bot for every bot, from its record", _review)
    p.add_argument("--answer", nargs="*", default=[], metavar="BOT.GATE=OUTCOME",
                   help="your calls: launch_watch.trust_bot=ask_outward launch_watch.keep_bot=keep")
    p = cmd("verdict", "Your trust or keep call on a bot: kept as a precedent, and applied", _verdict)
    p.add_argument("slug")
    p.add_argument("which", choices=["trust", "keep"])
    p.add_argument("outcome", choices=sorted(set(TRUST) | set(KEEP)))
    p = cmd("routine", "Install the bot's routine (launchd on a Mac; elsewhere the cron line to add)",
            lambda a: install_routine(orchestrator(a).bot(a.slug), remove=a.remove))
    p.add_argument("slug")
    p.add_argument("--remove", action="store_true", help="take the routine away")


def _answer(words: List[str]) -> Any:
    """`continue`'s answer: none (asked at the terminal), one word, or a batch's N=outcome words."""
    if not words:
        return None
    return words[0] if len(words) == 1 else list(words)


def _outcome(a: argparse.Namespace) -> Any:
    if len(a.rest) > 2:
        raise BotError("outcome takes [item] outcome: at most two words after the gate")
    item, outcome = (a.rest[0], a.rest[1]) if len(a.rest) == 2 else (None, a.rest[0])
    return orchestrator(a).runner(a.slug).outcome(a.run_id, a.gate, item, outcome)


def _check(a: argparse.Namespace) -> Any:
    bot = Bot.load(Path(a.folder))
    return {"bot": bot.slug, "ok": True, "touches": bot.touches, "gates": list(bot.gates), "models": bot.models()}


def _install(a: argparse.Namespace) -> Any:
    return orchestrator(a).install(a.source, job=a.job)


def _new(a: argparse.Namespace) -> Any:
    return orchestrator(a).new(a.job, recurs=a.recurs, touches=a.touches, answer=a.answer)


def _status(a: argparse.Namespace) -> Any:
    o = orchestrator(a)
    return o.runner(a.slug).status() if a.slug else o.status()


def _review(a: argparse.Namespace) -> Any:
    answers = {}
    for given in a.answer:
        key, sep, value = given.partition("=")
        if not sep or "." not in key:
            raise BotError(f"{given}: an answer is BOT.GATE=OUTCOME, like launch_watch.trust_bot=ask_outward")
        answers[key] = value
    return orchestrator(a).review(answers)


def _verdict(a: argparse.Namespace) -> Any:
    allowed = TRUST if a.which == "trust" else KEEP
    if a.outcome not in allowed:
        raise BotError(f"a {a.which} verdict is one of {', '.join(allowed)}")
    return orchestrator(a).verdict(a.slug, a.which, a.outcome)
