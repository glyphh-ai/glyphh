"""Bots that were loops of steps, converted to agents (docs/specs/bot-agent-loop.md, 9), and an orchestrator for
every org that has none. Run by the schema step after the migrations, each time it runs; a bot is converted once
(only a bot whose spec still has a loop is touched).

A bot keeps everything the person chose and everything its decisions learned: its name, cat, model, effort,
permission mode, schedule, where it runs, folders, connections and tools, decisions, connector tools, runs. Its
spec as it was is kept in `old_spec`. A bot whose loop is a library template's gets that template's plugin, standing
task and examples, and the template's new instructions unless the person had written their own; the notes the
template gave it are in the plugin now, and a note the person wrote or changed stays theirs. Any other bot gets a
note, `how-it-works`, written from its loop in order, so its agent knows the job its steps did.

Two things of a decision and a connector tool named a step of the loop, and are mended so they still work: a case
that read a step's data (`$report.title`) reads the item `decide` is handed (`$item.title`), and a connector tool's
`verdicts` names the decision its step made (none, when the step made no decision). A run that waited on the person
waited in the old engine: it is failed, saying the bot was updated."""

import hashlib
import json
import re
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Bot, BotRun, Org
from glyphh_server.ops.bots import installed, orchestrator, packages, runs
from glyphh_server.ops.bots.store import SPEC

# the library's templates as they were: their loop's steps (id, and the tool a step ran), and their instructions
# then (sha256, 16 hex)
WERE: dict[tuple[str, ...], tuple[str, str]] = {
    ("mail=gmail-find-email", "worth", "digest", "send=gmail-send-email"): ("inbox-triage", "abc9fc7308b43255"),
    ("events=google_calendar-list-events", "prep", "briefs", "page=notion-create-page"): (
        "meeting-prep", "68a3b7e6b1140d30"),
    ("prs=github-search-issues-and-pull-requests", "today", "digest", "slack=slack-send-message"): (
        "pr-review-digest", "5bd7417f17f42acb"),
    ("tickets=gmail-find-email", "urgency", "post", "slack=slack-send-message"): (
        "support-triage", "18aaf81b631ef056"),
    ("leads", "score", "rows", "sheet=google_sheets-add-multiple-rows"): ("lead-scoring", "d3c880d3e292a870"),
    ("page=fetch", "read", "brief"): ("news-brief", "2b9128e37a4d9884"),
    ("merged=github-search-issues-and-pull-requests", "report", "ready", "page=notion-create-page"): (
        "weekly-report", "dc6519ca8ac1b014"),
    ("mail=inbox_applications", "source", "fit", "probe=probe_generated", "made", "verdicts=screen_verdicts",
     "label=inbox_label"): ("resume-screener", "bfc6ec59dc63eb92"),
}  # fmt: skip
# the notes those templates gave a bot (sha256, 16 hex): each is a skill of the template's plugin now
THEIR_NOTES: frozenset[str] = frozenset({
    "e352b4422da9a81a", "06b1936510a11ea5", "75dba25271b66721", "41e15cec2c601db1", "9fdc3e5482742fa8",
    "c9f231943a4359cf", "b8b7d7bdfb54e633",
})  # fmt: skip
LIMITS: tuple[str, ...] = ("turns", "seconds", "tokens", "runs_per_day")  # a loop's other limits were its steps'
UPDATED: str = "The bot was updated while this run waited: run it again."
NOTE: str = "how-it-works"
STANDING: str = "Do your job now."
HEAD: str = (
    "---\nname: how-it-works\ndescription: The job this bot does, step by step, as it was set up. Read it before "
    "doing the job.\n---\n\nDo the job in this order. Use the tool each step names (its key, with - as _), and "
    "decide only with the decide tool.\n\n"
)
ORCHESTRATED = text(
    "UPDATE projects p SET orchestrator = b.id FROM bots b "
    "WHERE b.org_id = p.org_id AND b.role = 'orchestrator' AND p.orchestrator IS DISTINCT FROM b.id"
)
REF: re.Pattern[str] = re.compile(r"\$([A-Za-z_]\w*)((?:\.\w+)*)")


def _sha(said: str) -> str:
    return hashlib.sha256(said.encode()).hexdigest()[:16]


def _steps(bot: Any) -> list[dict[str, Any]]:
    loop = bot.spec.get("loop")
    return [s for s in loop if isinstance(s, dict)] if isinstance(loop, list) else []


def item_case(case: Any) -> Any:
    """A decision's case as `decide` fills it, from the item alone. What read a step's data reads the item: the
    step's data is the item when the case read one step only (`$report.title`: `$item.title`), else it is the
    item's field of that name (`$a.x`: `$item.a.x`)."""
    said = json.dumps(case)
    heads = {m.group(1) for m in REF.finditer(said)}
    lone = len(heads) == 1

    def of_item(m: re.Match[str]) -> str:
        if m.group(1) == "item":
            return m.group(0)
        return f"$item{m.group(2)}" if lone else f"$item.{m.group(1)}{m.group(2)}"

    return json.loads(REF.sub(of_item, said))


def _fields(case: Any) -> list[str]:
    """The fields of an item a case reads, by name."""
    return sorted({m.group(2).split(".")[1] for m in REF.finditer(json.dumps(case)) if m.group(2)})


def _line(step: dict[str, Any], gates: dict[str, Any]) -> str:
    """One step of a loop, as a sentence for the agent."""
    given = f" with {json.dumps(step['input'])}" if step.get("input") is not None else ""
    ask = " Ask the person first." if step.get("approval") else ""
    if "run" in step:
        return f"Use {step['run']}{given}.{ask}"
    if "gate" in step:
        of = f"each item of {step['each']}" if step.get("each") else "one item, what the steps before found"
        gate = gates.get(step["gate"])
        fields = _fields(gate.get("case")) if isinstance(gate, dict) else []
        needs = f" Each item needs its {', '.join(fields)}." if fields else ""
        return f"Decide `{step['gate']}` for {of} (the decide tool), and go on with what it answers.{needs}"
    if "agent" in step:
        return f"{str(step['agent']).strip()}{ask}"
    return f"Do the step {step.get('id', '')}."


def note(bot: Any, gates: dict[str, Any]) -> str:
    """A bot's loop as the note its agent reads: each step in order, in words. Where a step read an earlier step's
    data (`$id`), the words still say so: the agent has that data from the tool it just used."""
    lines = [f"{i}. {_line(s, gates)}" for i, s in enumerate(_steps(bot), 1)]
    return HEAD + "\n".join(lines) + "\n\n`$input` is what the person said; `$name` is what that step found.\n"


def template_of(bot: Any) -> packages.Package | None:
    """The library template the bot was installed from: the one whose loop had these steps and tools."""
    shape = tuple(f"{s.get('id')}={s['run']}" if "run" in s else str(s.get("id")) for s in _steps(bot))
    found = WERE.get(shape)
    return packages.library().get(found[0]) if found else None


def _own_words(bot: Any) -> bool:
    """Whether the person changed the instructions the template gave the bot."""
    return _sha(bot.instructions) not in {then for _, then in WERE.values()}


def _spec(bot: Any) -> dict[str, Any]:
    """The bot's spec as an agent's: no loop, each decision's case read from its item, the limits a run has. What a
    loop said it `touches` goes with the loop: the SDK holds a bot that sends to a step with an approval, and an
    agent has no steps (its permission mode is what asks)."""
    spec = {k: v for k, v in bot.spec.items() if k in SPEC}  # `touches` is not a key of a bot's spec any more
    if isinstance(spec.get("gates"), dict):
        mended = {n: {**g, "case": item_case(g["case"])} if isinstance(g, dict) and "case" in g else g
                  for n, g in spec["gates"].items()}  # fmt: skip
        spec["gates"] = mended
    if isinstance(spec.get("limits"), dict):
        spec["limits"] = {k: v for k, v in spec["limits"].items() if k in LIMITS}
    return spec


def _tools(bot: Any, gates: dict[str, Any], theirs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The bot's connector tools: the template's as they are now (`theirs`), then the bot's own, each one's
    `verdicts` the decision its step made (none, when that step made no decision)."""
    made = {str(s.get("id")): s["gate"] for s in _steps(bot) if s.get("gate") in gates}
    names = {t["name"] for t in theirs}
    own = [t for t in bot.connector_tools or [] if t.get("name") not in names]
    return [*theirs, *({**t, "verdicts": made.get(t["verdicts"])} if t.get("verdicts") else t for t in own)]


def changes(bot: Any) -> dict[str, Any]:
    """What converting the bot changes on its row (its plugin, when it is a template's, is kept beside)."""
    spec = _spec(bot)
    gates = spec["gates"] if isinstance(spec.get("gates"), dict) else {}
    task = str((bot.schedule or {}).get("input") or "").strip()
    out: dict[str, Any] = {"old_spec": bot.spec, "spec": spec, "task": task or STANDING}
    package = template_of(bot)
    if package is None:
        skills = {**bot.skills, NOTE: note(bot, gates)}
        return out | {"skills": skills, "connector_tools": _tools(bot, gates, [])}
    side = package.sidecar
    more = {"hosts": sorted({*side.hosts, *(spec.get("hosts") or [])}), "builtins": side.builtins}
    out["spec"] = spec | {k: v for k, v in more.items() if v}
    out |= {"task": task or side.task, "examples": side.examples}
    out["skills"] = {name: said for name, said in bot.skills.items() if _sha(said) not in THEIR_NOTES}
    out["connector_tools"] = _tools(bot, gates, side.connector_tools)
    if not _own_words(bot):
        out["instructions"] = side.bot.instructions
    return out


async def convert(conn: AsyncConnection) -> dict[str, int]:
    """Every org given its orchestrator, every project pointed at it, every loop bot converted. How many of each."""
    without = select(Org.id).where(~select(Bot.id).where(Bot.org_id == Org.id, Bot.role == orchestrator.ROLE).exists())
    orgs = list((await conn.scalars(without)).all())
    for org_id in orgs:
        await orchestrator.ensure(conn, org_id)
    await conn.execute(ORCHESTRATED)
    loops = list(await conn.execute(select(Bot).where(Bot.spec.has_key("loop"))))
    for bot in loops:
        await conn.execute(update(Bot).where(Bot.id == bot.id).values(**changes(bot)))
        package = template_of(bot)
        if package is not None:
            await installed.keep(conn, bot, package)
        waited = (BotRun.bot_id == bot.id, BotRun.status.in_(("needs_input", "dispatched")))
        ended = {"status": "failed", "error": UPDATED, "question": {}, "finished_at": runs.now()}
        await conn.execute(update(BotRun).where(*waited).values(**ended))
    return {"orchestrators": len(orgs), "bots": len(loops)}
