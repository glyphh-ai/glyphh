"""Glyphh's built-in tools: steps any bot may run beside `fetch` and its connections' Pipedream actions. They are
Glyphh's own code, the same on Glyphh cloud and for a bot on a rrotor (whose steps call them through the server's tool
endpoint, ops/bots/tool_calls.py), so a cloud bot still runs no code of its own. The Resume Screener's:

- `inbox_applications` `{given?, q?, most?}`: the person's own application when `given` holds one (a resume's text,
  or `{resume, letter?, sender?, role?}`), else the new applications in the bot's Gmail (`q`, a Gmail search; at most
  `most`), each read whole and made into an applicant (ops/bots/applicants.py); `{applications, rejected, polled}`.
- `probe_generated` `{applications, gate}`: the gate probed for each application (ops/bots/probe.py), on the runner's
  thread with the bot's own Ada; `{generated, human, reference}`. On a rrotor (no seeded reference there) all go on.
- `screen_verdicts` `{applications, rejected, source, fit, probe, made}`: the gates' calls put together
  (ops/bots/verdicts.py).
- `inbox_label` `{verdicts, rejected}`: each screened message labelled in Gmail with its verdict."""

import asyncio
import contextlib
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from glyphh_server.ops.bots import applicants, probe, verdicts
from glyphh_server.ops.bots.gmail import Gmail
from glyphh_server.ops.bots.pipedream import Pipedream

Call = Callable[[dict[str, Any]], Awaitable[Any]]
NAMES: tuple[str, ...] = ("inbox_applications", "probe_generated", "screen_verdicts", "inbox_label")
ON_RUNNER: dict[str, Callable[[Any, Any], Any]] = {"probe_generated": probe.probed}
QUERY: str = "in:inbox -label:screened newer_than:14d"
MOST: int = 25
NO_GMAIL: str = "The bot has no Gmail connection to read: connect Gmail and give the bot its connection."


def handed(given: Any) -> dict[str, Any] | None:
    """The application the person handed in, as {resume, ...}; None when there is none (poll the inbox)."""
    if isinstance(given, str) and given.strip().startswith("{"):
        with contextlib.suppress(ValueError):
            given = json.loads(given)
    if isinstance(given, dict):
        return given if str(given.get("resume") or given.get("letter") or "").strip() else None
    return {"resume": given} if isinstance(given, str) and given.strip() else None


def _given_id(app: dict[str, Any]) -> str:
    return "given-" + hashlib.sha256(json.dumps(app, sort_keys=True).encode()).hexdigest()[:10]


def _answer(made: list[tuple[Any, Any]], polled: int) -> dict[str, Any]:
    """Each (applicant, why not) made, as the step's data."""
    return {"applications": [a for a, _ in made if a], "rejected": [w for _, w in made if w], "polled": polled}


async def _polled(gmail: Gmail | None, q: str, most: int) -> dict[str, Any]:
    if gmail is None:
        raise ValueError(NO_GMAIL)
    ids = await gmail.ids(q, most)
    made = [await asyncio.to_thread(applicants.of_mail, await gmail.read(mid)) for mid in ids]
    return _answer(made, len(ids))


def _inbox(gmail: Gmail | None) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        app = handed(given.get("given"))
        if app is not None:
            return _answer([await asyncio.to_thread(applicants.of_given, _given_id(app), app)], 0)
        most = given.get("most") if isinstance(given.get("most"), int) else MOST
        return await _polled(gmail, str(given.get("q") or QUERY), max(1, min(most, 100)))

    return call


def _label(gmail: Gmail | None) -> Call:
    async def call(given: dict[str, Any]) -> Any:
        marks = verdicts.marks(given)
        if not marks:
            return {"labelled": {}}
        if gmail is None:
            raise ValueError(NO_GMAIL)
        return {"labelled": await gmail.label(marks)}

    return call


async def _merged(given: dict[str, Any]) -> Any:
    return verdicts.merged(given)


async def _unprobed(given: dict[str, Any]) -> Any:
    return probe.unprobed(given)


def made(pd: Pipedream, org_id: uuid.UUID, gmail_account: str | None) -> dict[str, Call]:
    """The built-in tools for one bot's go: its Gmail the first Gmail connection in its scope (None: it has none)."""
    gmail = Gmail(pd, org_id, gmail_account) if gmail_account else None
    return {"inbox_applications": _inbox(gmail), "probe_generated": _unprobed, "screen_verdicts": _merged,
            "inbox_label": _label(gmail)}  # fmt: skip
