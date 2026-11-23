"""Create with AI (docs/specs/bots.md, 9): the bot maker, Claude drafting a bot from what the person says they want. It
asks short questions until it knows the job, then drafts the whole bot (name, summary, cat, instructions, model, its
standing task and examples, what it decides, its notes, and the apps it needs), checked as a bot being made; a draft the
check finds wrong is sent back to Claude once to fix. The apps it needs are matched to the org's connections (its
first of each app), the ones not connected named. Nothing is made: POST /v1/bots makes the draft. Claude is the bots'
own, on the org's key or Glyphh's, metered either way (ops/bots/goes.py)."""

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any

from glyphh.bots import BotError
from pydantic import ValidationError
from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError, Unavailable
from glyphh_server.models import Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import prices, shape, store
from glyphh_server.ops.bots.guide import GUIDE
from glyphh_server.ops.bots.maker_views import BotDraft, DraftIn, DraftView
from glyphh_server.ops.bots.views import LOOK_PARTS, ScopeIn

LOOKS: str = (
    "head classic|spiky|tall|folded|round; tail spike|bolt|curl|long; eye dot|side|big|sleepy|heart|star; "
    "extra none|antenna|cape|bolt; accessory none|headphones|beanie|cap|glasses|shades|bow|scarf|crown|chain; "
    "pose stand|lean|hop|turn"
)
ANSWER: str = """\
You are Glyphh's bot maker. The person tells you what they want a bot to do; you make it with them. Ask one short,
plain question at a time until you know the job: what it watches or is given, what it does, what needs their yes,
how often. Two or three questions is usually enough; never more than five before drafting. Then draft the whole bot
and keep changing it as they ask. Write the way a friendly colleague talks: short, concrete, no jargon.

Answer with one JSON object and nothing else:
{"reply": "<what you say to the person: a question, or what you drafted and what to check>",
 "draft": null or {"name": "...", "summary": "<one line>", "look": {<its cat: one of each of LOOKS>},
   "instructions": "<who it is and how it works, as the guide says>", "model": "<one of MODELS>",
   "task": "<what it does when it runs on its own>", "examples": ["<a prompt a person might type>", ...],
   "spec": {<as the guide says>}, "skills": {"<name>": "<SKILL.md text: its know-how for one kind of work>"},
   "apps": [{"app": "<Pipedream app slug>", "tools": ["<tool key>", ...]}]}}
Give the draft only once you know enough, and then every time after, whole. The tools its instructions use are tools
of an app in apps. Tool keys are Pipedream action keys, the app's slug first (gmail-find-email, slack-send-message);
its instructions call each by its key with - as _ (gmail_find_email).
LOOKS: {looks}
MODELS: {models} (the default {default} unless the job is simple and frequent)
The org has these apps connected: {linked}. Prefer them; name any other app it truly needs.

How a bot is written:
{guide}"""


def system(linked: list[str]) -> str:
    return (
        ANSWER.replace("{looks}", LOOKS)
        .replace("{models}", ", ".join(prices.CLAUDE))
        .replace("{default}", prices.DEFAULT)
        .replace("{linked}", ", ".join(linked) or "none yet")
        .replace("{guide}", GUIDE)
    )


async def ask(bots: Any, org_id: Any, prompt_of: str, prompt: str) -> str:
    """Claude's answer to one prompt, on the bots' Claude (the org's key or Glyphh's, metered)."""
    claude, _ = await bots.claude_of(SimpleNamespace(org_id=org_id, model=prices.DEFAULT))
    try:
        got = await asyncio.to_thread(claude.answer, "glyphh-bot-maker", {"prompt": prompt_of}, prompt, seconds=180)
    except BotError as err:
        raise Unavailable(err.message, reason="claude") from err
    return str(got.text)


def transcript(body: DraftIn, problems: list[str]) -> str:
    said = "\n\n".join(f"{'Person' if m.role == 'user' else 'You'}: {m.content}" for m in body.messages)
    now = f"\n\nThe draft so far:\n{json.dumps(body.draft)}" if body.draft else ""
    fix = "\n\nYour last draft has these problems; fix them all:\n- " + "\n- ".join(problems) if problems else ""
    return f"The conversation so far:\n\n{said}{now}{fix}\n\nAnswer with the JSON object."


def parsed(text: str) -> tuple[str, dict[str, Any] | None]:
    """Claude's reply and draft; a reply that is not the JSON asked for is taken as the reply alone."""
    found = re.search(r"\{.*\}", text, re.S)
    try:
        got = json.loads(found.group(0)) if found else None
    except json.JSONDecodeError:
        got = None
    if not isinstance(got, dict):
        return text.strip(), None
    draft = got.get("draft")
    return str(got.get("reply") or "").strip(), draft if isinstance(draft, dict) else None


def problems_of(draft: BotDraft) -> list[str]:
    """What the check of a bot being made finds wrong with the draft, and what its task and examples run over."""
    scopes = [{"connection_id": a.app, "tools": a.tools} for a in draft.apps]
    over = shape.limits(draft.task, draft.examples)
    try:
        slug = store.slugify(draft.name)
        store.checked(SimpleNamespace(**draft.model_dump(), slug=slug, scopes=scopes, state=None))
    except GlyphhError as err:
        return [*(err.detail.get("problems") or [err.message]), *over]
    return over


def shaped(raw: dict[str, Any], linked: dict[str, Any], before: dict[str, Any] | None) -> BotDraft | list[str]:
    """The draft as a bot to make, scoped to the org's connections; or what is wrong with its shape."""
    model = raw.get("model") if raw.get("model") in prices.CLAUDE else prices.DEFAULT
    look = {k: str(v)[:40] for k, v in (raw.get("look") or {}).items() if k in LOOK_PARTS}
    mascot = str((before or {}).get("mascot") or "")
    try:
        draft = BotDraft.model_validate({**raw, "model": model, "look": look, "mascot": mascot, "connections": []})
    except ValidationError as err:
        return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()]
    draft.connections = [ScopeIn(connection_id=linked[a.app], tools=a.tools) for a in draft.apps if a.app in linked]
    return draft


async def linked_apps(bots: Any, who: Principal) -> dict[str, Any]:
    """The org's first connection of each app it has connected."""
    async with bots.engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        rows = await conn.execute(select(Connection.app, Connection.id).order_by(Connection.created_at))
    linked: dict[str, Any] = {}
    for app, id in rows:
        linked.setdefault(app, id)
    return linked


async def _turn(bots: Any, who: Principal, body: DraftIn, linked: dict[str, Any], problems: list[str]) -> DraftView:
    reply, raw = parsed(await ask(bots, who.org_id, system(sorted(linked)), transcript(body, problems)))
    draft = shaped(raw, linked, body.draft) if raw is not None else None
    if isinstance(draft, list):
        return DraftView(reply=reply, draft=None, problems=draft, missing_apps=[])
    found = problems_of(draft) if draft else []
    missing = sorted({a.app for a in draft.apps} - set(linked)) if draft else []
    return DraftView(reply=reply or "Here is a draft.", draft=draft, problems=found, missing_apps=missing)


async def draft(bots: Any, who: Principal, body: DraftIn) -> DraftView:
    """The bot maker's next turn: a question, or the bot drafted and checked (sent back once to fix what is wrong)."""
    linked = await linked_apps(bots, who)
    got = await _turn(bots, who, body, linked, [])
    if got.problems:
        again = await _turn(bots, who, body, linked, got.problems)
        got = again if again.draft is not None or got.draft is None else got
    return got
