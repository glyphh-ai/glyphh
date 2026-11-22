"""What a run says when it ends: a plain summary in the bot's own step and decision names, never the runner's line;
and a hint when the text it was given did not fit the bot."""

from types import SimpleNamespace
from typing import Any

from glyphh_server.ops.bots import said, templates
from glyphh_server.ops.bots.runs_words import joined, plain, sentence

LOOP: list[dict[str, Any]] = [
    {"id": "prs", "run": "github-search", "input": {"query": "$input"}},
    {"id": "today", "gate": "today", "each": "$prs.ret.items", "on": {"empty:today": "end"}},
    {"id": "digest", "agent": "Write the digest: $today.today"},
    {"id": "slack", "run": "slack-send-message", "input": {"text": "$digest"}},
]
SPEC: dict[str, Any] = {"loop": LOOP}
EACH = "gate today: today 0, later 0; the run ends here"


def run(status: str = "done", error: str = "", given: str = "", **data: Any) -> Any:
    return SimpleNamespace(status=status, error=error, input=given, data=data)


def test_words() -> None:
    assert (sentence("  it broke: "), sentence(""), sentence("Fine!")) == ("It broke.", "", "Fine!")
    assert (joined([]), joined(["a"]), joined(["a", "b"])) == ("", "a", "a and b")
    assert joined(["a", "b", "c"]) == "a, b and c"
    assert plain("gate worth: the Gates of the loop") == "decision worth: the decisions of the steps"


def test_a_run_that_is_going_says_nothing_and_one_waiting_says_so() -> None:
    for status in ("queued", "running", "dispatched"):
        assert said.summary(run(status), SPEC) == "" and said.hint(run(status, given="x"), SPEC, "B", "does") == ""
    assert said.summary(run("needs_input"), SPEC) == "It is waiting on your answer."
    assert said.hint(run("needs_input", given="x"), SPEC, "B", "does") == ""


def test_the_decision_with_nothing_to_decide_is_said_in_step_names_not_the_runners_line() -> None:
    empty = run(error=EACH, today={"today": [], "later": [], "decisions": [], "asked": 0})
    told = said.summary(empty, SPEC)
    assert told == "Nothing to decide: prs found nothing, so it stopped before digest and slack."
    assert "gate" not in told and "run ends here" not in told
    sourceless = {"loop": [{"id": "today", "gate": "today", "each": "", "on": {"empty:today": "end"}}]}
    assert said.summary(run(error=EACH, today={}), sourceless) == "Nothing to decide: there was nothing, so it stopped."


def test_a_decision_that_left_none_wanted_says_what_it_decided() -> None:
    some = run(error=EACH, today={"today": [], "later": [{"id": 1}, {"id": 2}], "decisions": [1, 2]})
    assert said.summary(some, SPEC) == (
        "It decided 2 (0 today and 2 later); none came out today, so it stopped before digest and slack."
    )
    any_rule = {"loop": [{"id": "today", "gate": "today", "each": "$x", "on": {"any:later": "end"}}]}
    assert said.summary(some, any_rule) == "It decided 2 (0 today and 2 later); that ends the run, so it stopped."


def test_a_steps_own_empty_sentence_is_the_summary() -> None:
    spec = {"loop": [LOOP[0], {**LOOP[1], "empty": "no pull request needs you today"}, *LOOP[2:]]}
    assert said.summary(run(error=EACH), spec) == "No pull request needs you today."
    for name in ("pr-review-digest", "news-brief", "lead-scoring"):
        loop = templates.one(name).spec["loop"]
        assert all(s.get("empty") for s in loop if "end" in (s.get("on") or {}).values()), name


def test_one_decision_and_a_requirement_that_end_the_run() -> None:
    spec = {
        "loop": [
            {"id": "report", "agent": "Write it"},
            {"id": "ready", "gate": "ready_to_file", "on": {"file": "page", "hold": "end"}},
            {"id": "page", "run": "notion", "requires": "len($report) > 0", "otherwise": "end"},
        ]
    }
    held = run(error="gate ready_to_file said hold: the run ends here")
    assert said.summary(held, spec) == "It decided hold on ready to file, so it stopped before page."
    unmet = run(error="page requires len($report) > 0: it does not hold, the run ends here")
    assert said.summary(unmet, spec) == "Page had nothing to work on, so it stopped there."
    gone = run(error="gate removed said no: the run ends here")
    assert said.summary(gone, spec) == "It stopped early: there was nothing more for it to do."


def test_the_bots_own_reason_and_the_other_ends() -> None:
    assert said.summary(run(error="the program ended the run: nothing new since monday"), SPEC) == (
        "Nothing new since monday."
    )
    assert said.summary(run(), SPEC) == "It finished all 4 steps: prs, today, digest and slack."
    assert said.summary(run(), {"loop": [LOOP[0], "junk"]}) == "It finished."
    assert said.summary(run("failed", "cancelled"), SPEC) == "Cancelled before it finished."
    assert said.summary(run("failed", "interrupted by a restart"), SPEC).startswith("It was cut off by a restart")
    assert said.summary(run("failed", "step today: gate today has no model"), SPEC) == (
        "It failed: Step today: decision today has no model."
    )
    assert said.summary(run("failed"), SPEC) == "It failed."
    assert said.summary(run("skipped", "the bot is paused"), SPEC) == "It did not run: The bot is paused."
    assert said.summary(run("skipped"), SPEC) == "It did not run."


def test_a_task_that_does_not_fit_is_answered_with_what_the_bot_does_and_takes() -> None:
    about = "Finds the pull requests waiting on your review"
    off = run(error=EACH, given="fetch the latest ai news")
    assert said.hint(off, SPEC, "PR Review Digest", about) == (
        "PR Review Digest does one job: finds the pull requests waiting on your review. "
        "What you type is handed to its first step as it is."
    )
    spec = {**SPEC, "takes": "a GitHub search", "try": "is:pr is:open review-requested:@me"}
    assert said.hint(off, spec, "PR Review Digest", "").endswith(
        "does one job. What you type is used as a GitHub search, for example: is:pr is:open review-requested:@me."
    )
    no_example = said.hint(run("failed", "x", "y"), {**spec, "try": 3}, "B", "")
    assert "What you type is used as a GitHub search." in no_example
    assert said.hint(run(given="is:pr"), spec, "B", about) == ""  # it read its text and went the whole way
    assert said.hint(run(error=EACH), spec, "B", about) == ""  # given nothing
    fixed = {"loop": [{"id": "page", "run": "fetch", "input": "https://example.com"}]}
    assert said.hint(run(given="fetch the latest ai news"), fixed, "News Brief", "Reads the front page") == (
        "News Brief does one job: reads the front page. It does not read what you type: it does that job each time "
        "it runs."
    )
    assert said.hint(run(given="x"), fixed, "B", "PRs, ranked").startswith("B does one job: PRs, ranked.")
