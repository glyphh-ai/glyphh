"""What a run says when it has no words of its own (ops/bots/said.py; docs/specs/bot-agent-loop.md, 10): one plain
sentence for a run that failed, was cancelled, was cut off, did not run or waits on the person, never the engine's own
words; nothing while it is going, and nothing for a run that ended on the bot's answer."""

from types import SimpleNamespace
from typing import Any

from glyphh_server.ops.bots import said
from glyphh_server.ops.bots.runs_words import plain, sentence


def run(status: str = "done", error: str | None = "", output: str | None = "") -> Any:
    return SimpleNamespace(status=status, error=error, output=output)


def test_words() -> None:
    assert (sentence("  it broke: "), sentence(""), sentence("Fine!")) == ("It broke.", "", "Fine!")
    assert (sentence("is it?"), sentence("done."), sentence(" ; ")) == ("Is it?", "Done.", "")
    assert plain("gate worth: the Gates of the loop") == "decision worth: the decisions of the steps"


def test_a_run_that_is_going_says_nothing_and_one_waiting_says_so() -> None:
    for status in ("queued", "running", "dispatched"):
        assert said.summary(run(status)) == "" and said.summary(run(status, "an old error")) == ""
    assert said.summary(run("needs_input")) == "It is waiting on your answer."


def test_a_run_that_answered_needs_no_summary_and_a_silent_one_says_so() -> None:
    assert said.summary(run(output="Two letters worth answering.")) == ""
    assert said.summary(run(output="Sent.", error="a note it left")) == ""  # its words are what it says
    assert said.summary(run(error="It finished without saying anything.")) == "It finished without saying anything."
    assert said.summary(run(error="nothing new since monday", output="  ")) == "Nothing new since monday."
    assert said.summary(run()) == "It finished." and said.summary(run(error=None, output=None)) == "It finished."


def test_a_run_that_failed_says_why_in_plain_words() -> None:
    assert said.summary(run("failed", "cancelled")) == "Cancelled before it finished."
    assert said.summary(run("failed", "interrupted by a restart")) == (
        "It was cut off by a restart before it finished. Run it again."
    )
    assert said.summary(run("failed", "gate today has no model")) == "It failed: Decision today has no model."
    assert said.summary(run("failed", "It ran out of time (300 seconds).")) == (
        "It failed: It ran out of time (300 seconds)."
    )
    assert said.summary(run("failed")) == "It failed." and said.summary(run("failed", None)) == "It failed."


def test_a_run_that_did_not_run_says_why() -> None:
    assert said.summary(run("skipped", "the bot is paused")) == "It did not run: The bot is paused."
    assert said.summary(run("skipped", "  ")) == "It did not run."
