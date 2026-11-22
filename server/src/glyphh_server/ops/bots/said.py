"""What a run says to the person when it ends: `summary`, one plain sentence in the bot's own step and decision names
(nothing to decide, decided and stopped, finished, failed, cancelled, waiting), and `hint`, said when the text the
run was given did not fit the bot: what the bot does and what to give it. A bot's loop is fixed (its steps run in
order; nothing reads free text but the steps that name `$input`), so a task that does not fit cannot be answered by
the bot: the turn says so instead of ending silently. The runner's own lines (`gate today: today 0, later 0; the run
ends here`) are never the answer: they stay in the run's log. A step that can end the run early may carry `empty`,
the bot's own sentence for it; a bot may carry `takes` and `try` (what its `$input` is used as, an example)."""

import json
import re
from typing import Any

from glyphh_server.ops.bots.runs_words import INTERRUPTED, joined, named, plain, sentence

ENGINE_EACH: re.Pattern[str] = re.compile(r"^gate (\S+): .*; the run ends here$")
ENGINE_ONE: re.Pattern[str] = re.compile(r"^gate (\S+) said (\S+): the run ends here$")
ENGINE_REQUIRES: re.Pattern[str] = re.compile(r"^(\S+) requires .*the run ends here$")
PROGRAM_END: re.Pattern[str] = re.compile(r"^the program ended the run:\s*", re.I)
WORKING: frozenset[str] = frozenset({"queued", "running", "dispatched"})


def steps(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in spec.get("loop") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)]


def _after(spec: dict[str, Any], sid: str) -> str:
    """The steps the run never reached, named: " before digest and slack"; nothing when it was the last."""
    ids = [s["id"] for s in steps(spec)]
    rest = ids[ids.index(sid) + 1 :]
    return f" before {joined([named(i) for i in rest])}" if rest else ""


def _lists(out: Any) -> dict[str, list[Any]]:
    """A per-item decision's outcomes, each with its items."""
    found = out if isinstance(out, dict) else {}
    return {k: v for k, v in found.items() if isinstance(v, list) and k != "decisions"}


def _each(spec: dict[str, Any], step: dict[str, Any], out: Any) -> str:
    """A decision over many items that ended the run: nothing to decide, or what it decided and why it stopped."""
    lists, sid = _lists(out), step["id"]
    total = sum(len(v) for v in lists.values())
    source = str(step.get("each") or "").lstrip("$").split(".")[0]
    if total == 0:
        found = f"{named(source)} found nothing" if source else "there was nothing"
        return f"Nothing to decide: {found}, so it stopped{_after(spec, sid)}."
    counts = joined([f"{len(v)} {named(k)}" for k, v in lists.items()])
    wanted = next((r.partition(":")[2] for r in (step.get("on") or {}) if r.startswith("empty:")), "")
    why = f"none came out {named(wanted)}" if wanted and not lists.get(wanted) else "that ends the run"
    return f"It decided {total} ({counts}); {why}, so it stopped{_after(spec, sid)}."


def _step(spec: dict[str, Any], key: str, name: str) -> dict[str, Any] | None:
    return next((s for s in reversed(steps(spec)) if s.get(key) == name), None)


def _ended(spec: dict[str, Any], run: Any) -> str:
    """Why a run that is done ended early, in the bot's words when it has them, else from its step names."""
    reason = str(run.error).strip()
    each, one, requires = ENGINE_EACH.match(reason), ENGINE_ONE.match(reason), ENGINE_REQUIRES.match(reason)
    found = each or one or requires
    if found is None:  # the bot's own sentence (a step's `empty`, its code's `_end`)
        return sentence(plain(PROGRAM_END.sub("", reason)))
    step = _step(spec, "id" if requires else "gate", found.group(1))
    if step is None:
        return "It stopped early: there was nothing more for it to do."
    if isinstance(step.get("empty"), str) and step["empty"].strip():
        return sentence(step["empty"])
    if requires:
        return f"{sentence(named(step['id']))[:-1]} had nothing to work on, so it stopped there."
    if each:
        return _each(spec, step, (run.data or {}).get(step["id"]))
    return f"It decided {named(found.group(2))} on {named(step['gate'])}, so it stopped{_after(spec, step['id'])}."


def _failed(error: str) -> str:
    if error == "cancelled":
        return "Cancelled before it finished."
    if INTERRUPTED in error:
        return "It was cut off by a restart before it finished. Run it again."
    return f"It failed: {sentence(plain(error))}" if error else "It failed."


def summary(run: Any, spec: dict[str, Any]) -> str:
    """What happened, in a plain sentence; empty while the run is going."""
    status, error = str(run.status), str(run.error or "").strip()
    if status in WORKING:
        return ""
    if status == "needs_input":
        return "It is waiting on your answer."
    if status == "skipped":
        return f"It did not run: {sentence(plain(error))}" if error else "It did not run."
    if status == "failed":
        return _failed(error)
    if error:
        return _ended(spec, run)
    ids = [named(s["id"]) for s in steps(spec)]
    return f"It finished all {len(ids)} steps: {joined(ids)}." if len(ids) > 1 else "It finished."


def reads_input(spec: dict[str, Any]) -> bool:
    return bool(re.search(r"\$input\b", json.dumps(spec.get("loop") or [])))


def _said(spec: dict[str, Any], key: str) -> str:
    value = spec.get(key)
    return value.strip() if isinstance(value, str) else ""


def hint(run: Any, spec: dict[str, Any], name: str, about: str) -> str:
    """When the run was given text and that text did not fit: what the bot does, and what to give it. Nothing for a
    run that is going or waiting, one given nothing, or one that read its text and went the whole way."""
    given, status = str(run.input or "").strip(), str(run.status)
    if not given or status in WORKING or status == "needs_input":
        return ""
    job = sentence(about)
    job = job[0].lower() + job[1:] if job[1:2].islower() else job  # after the colon: "finds ...", but "PRs ..." stays
    does = f"{name} does one job: {job}" if job else f"{name} does one job."
    if not reads_input(spec):
        return f"{does} It does not read what you type: it does that job each time it runs."
    if status == "done" and not str(run.error or "").strip():
        return ""
    takes, example = _said(spec, "takes"), _said(spec, "try")
    used = f"What you type is used as {takes}" if takes else "What you type is handed to its first step as it is"
    return f"{does} {used}{f', for example: {example}' if example else ''}."
