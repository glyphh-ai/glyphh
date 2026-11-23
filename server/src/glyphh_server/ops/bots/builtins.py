"""Glyphh's built-in tools: tools a bot's agent may have beside `fetch`, `decide` and its connections' Pipedream
actions, when its spec names them (`builtins`; ops/bots/agent/tools.py). They are Glyphh's own code, the same on
Glyphh cloud and for a bot on a rrotor (whose agent calls them through the server's tool endpoint,
ops/bots/tool_calls.py), so a cloud bot still runs no code of its own. The Resume Screener's:

- `inbox_applications` `{given?, q?, most?}`: the person's own application when `given` holds one (a resume's text,
  or `{resume, letter?, sender?, role?}`), else the new applications in the bot's Gmail (`q`, a Gmail search; at most
  `most`), each read whole and made into an applicant (ops/bots/applicants.py); `{applications, rejected, polled}`.
- `inbox_label` `{verdicts: [{id, verdict}], rejected: [{id}]}`: each screened message labelled in Gmail with its
  verdict (ops/bots/verdicts.py); `{labelled: {label: how many}}`.

What the agent does between the two is `decide`'s (ops/bots/agent/ada.py): the sender, the fit and how much was
generated, the last probed (ops/bots/probe.py)."""

import asyncio
import contextlib
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from glyphh_server.ops.bots import applicants, verdicts
from glyphh_server.ops.bots.gmail import Gmail
from glyphh_server.ops.bots.pipedream import Pipedream

Call = Callable[[dict[str, Any]], Awaitable[Any]]
QUERY: str = "in:inbox -label:screened newer_than:14d"
MOST: int = 25
NO_GMAIL: str = "The bot has no Gmail connection to read: connect Gmail and give the bot its connection."
ABOUT: dict[str, tuple[str, str, bool]] = {  # name: (title, what it does, read-only), as the agent is told
    "inbox_applications": (
        "Read the applications",
        "Read job applications: the one handed in `given` (a resume's text, or {resume, letter, sender, role}), "
        "else the new messages of the Gmail search `q` (at most `most`, 25 unless said). Answers {applications: one "
        "item per applicant, each with its id; rejected: [{id, from, subject, why}], the messages the sender checks "
        "refused; polled}.",
        True,
    ),
    "inbox_label": (
        "Label the screened mail",
        "Label each screened message in Gmail. Takes {verdicts: [{id, verdict}], rejected: [{id}]}; verdict is "
        "strong, borderline, poor or spam (any other, such as waiting, gets no label; a rejected message is "
        "labelled spam). Answers {labelled: {label: how many}}.",
        False,
    ),
}


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
    """Each (applicant, why not) made, as the tool answers."""
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


def made(pd: Pipedream, org_id: uuid.UUID, gmail_account: str | None) -> dict[str, Call]:
    """The built-in tools for one bot's go: its Gmail the first Gmail connection in its scope (None: it has none)."""
    gmail = Gmail(pd, org_id, gmail_account) if gmail_account else None
    return {"inbox_applications": _inbox(gmail), "inbox_label": _label(gmail)}
