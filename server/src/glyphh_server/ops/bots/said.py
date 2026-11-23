"""What a run says when it has no words of its own: `summary`, one plain sentence (it failed and why, it was
cancelled, it was cut off, it did not run, it waits on the person). A run that ended with the bot's answer needs
none: its `output` is the bot's final words (docs/specs/bot-agent-loop.md, 10)."""

from typing import Any

from glyphh_server.ops.bots.runs_words import INTERRUPTED, plain, sentence

WORKING: frozenset[str] = frozenset({"queued", "running", "dispatched"})


def _failed(error: str) -> str:
    if error == "cancelled":
        return "Cancelled before it finished."
    if INTERRUPTED in error:
        return "It was cut off by a restart before it finished. Run it again."
    return f"It failed: {sentence(plain(error))}" if error else "It failed."


def summary(run: Any) -> str:
    """What happened, in a plain sentence; empty while the run is going, and for a run that answered."""
    status, error = str(run.status), str(run.error or "").strip()
    if status in WORKING:
        return ""
    if status == "needs_input":
        return "It is waiting on your answer."
    if status == "skipped":
        return f"It did not run: {sentence(plain(error))}" if error else "It did not run."
    if status == "failed":
        return _failed(error)
    return "" if str(run.output or "").strip() else sentence(error) or "It finished."
