"""launch_watch through rrotor.testing: the same calls, waits and Results as on the rrotor, with no network: GitHub,
PyPI and npm answered by FakeHttp, the claude CLI by FakeCli."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from rrotor import CliResult
from rrotor.testing import FakeCli, FakeHttp, Harness

HERE = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((HERE / "glyphh.json").read_text())
ME = {"to": "you@example.com"}
SENT = json.dumps({"type": "result", "is_error": False, "result": "SENT 19a2b3c4d5"})


def program() -> ModuleType:
    spec = importlib.util.spec_from_file_location("launch_watch_program", HERE / "program.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def http(stars: int = 120) -> FakeHttp:
    issue = {
        "number": 7,
        "title": "Add a thing",
        "user": {"login": "someone"},
        "html_url": "https://github.com/glyphh-ai/glyphh/issues/7",
        "created_at": "2026-11-02T09:00:00Z",
    }
    return FakeHttp(
        {
            "https://api.github.com/repos/glyphh-ai/glyphh/issues": [issue],
            "https://api.github.com/repos/glyphh-ai/glyphh": {
                "stargazers_count": stars,
                "forks_count": 9,
                "open_issues_count": 4,
            },
            "https://pypistats.org/api/packages/glyphh/recent": {"data": {"last_day": 31, "last_week": 210}},
            "https://api.npmjs.org/downloads/point/last-day/": {"downloads": 12},
            "https://api.npmjs.org/downloads/point/last-week/": {"downloads": 80},
        }
    )


def harness(tmp_path: Path, claude: FakeCli, caller: str = "claude", day: int = 3, stars: int = 120) -> Harness:
    approvals = {name: set(f.get("approvals", [])) for name, f in MANIFEST["functions"].items()}
    return Harness(
        program(),
        tmp_path,
        approvals=approvals,
        http=http(stars),
        today=lambda: date(2026, 11, day),
        caller=caller,
        database=tmp_path / "db.sqlite3",
        clis={"claude": claude},
    )


def claude(answer: Any = SENT) -> FakeCli:
    return FakeCli(answer, allow=["-p *", "--print *"])  # the built-in claude CLI's own patterns, as far as -p goes


def test_the_manifest_runs_claude_and_no_longer_resend():
    assert MANIFEST["clis"] == ["claude"]
    assert "api.resend.com" not in MANIFEST["hosts"] and "secrets" not in MANIFEST


def test_from_claude_it_asks_then_has_claude_email_it_through_gmail(tmp_path):
    h = harness(tmp_path, claude())
    asked = h.call("morning", ME)
    assert (asked.status, asked.step) == ("needs_approval", "email")
    assert "Email this to you@example.com?" in str(asked.prompt) and h.cli_calls == []
    done = h.resume({"approved": True})
    assert done.status == "done" and done.data["emailed"] is True and done.data["email_id"] == "19a2b3c4d5"
    [(name, args, stdin)] = h.cli_calls
    assert (name, args[0], args[2:], stdin) == (
        "claude",
        "-p",
        ["--allowedTools", "mcp__claude_ai_Gmail__send_message", "--output-format", "json"],
        None,
    )
    prompt = args[1]
    assert "To: you@example.com" in prompt and f"Subject: {done.data['subject']}" in prompt
    assert done.data["summary"] in prompt and "Stars: 120" in prompt and "issue #7 Add a thing" in prompt
    emailed = h.call("history", {}).data["days"][0]
    assert (emailed["day"], emailed["emailed"], emailed["stars"]) == ("2026-11-03", True, 120)


def test_a_scheduled_run_sends_on_its_own(tmp_path):
    h = harness(tmp_path, claude(), caller="schedule")
    done = h.call("morning", {"to": "someone@glyphh.ai"})
    assert done.status == "done" and done.data["emailed"] is True
    assert "To: someone@glyphh.ai" in h.cli_calls[0][1][1]


def test_declined_it_keeps_the_numbers_and_sends_nothing(tmp_path):
    h = harness(tmp_path, claude())
    h.call("morning", ME)
    done = h.resume({"approved": False})
    assert done.data["emailed"] is False and h.cli_calls == []
    assert h.call("history", {}).data["days"][0]["emailed"] is False


def test_what_claude_could_not_send_is_kept_and_said(tmp_path):
    failed = json.dumps({"is_error": False, "result": "FAILED the Gmail connector is not connected"})
    h = harness(tmp_path, claude(failed), caller="schedule")
    done = h.call("morning", ME)
    assert done.data["emailed"] is False and done.data["error"] == "FAILED the Gmail connector is not connected"
    assert h.call("history", {}).data["days"][0]["emailed"] is False
    not_json = harness(tmp_path / "b", claude(CliResult(1, "", "Not logged in")), caller="schedule")
    (tmp_path / "b").mkdir(exist_ok=True)
    assert not_json.call("morning", ME).data["error"] == "claude exited 1: Not logged in"


def test_a_claude_cli_that_did_not_run_is_said(tmp_path):
    h = harness(tmp_path, FakeCli(SENT, allow=["--print *"]), caller="schedule")  # -p refused: E_CLI_DENIED
    assert h.call("morning", ME).data["error"].startswith("E_CLI_DENIED")


def test_the_next_day_shows_the_change(tmp_path):
    harness(tmp_path, claude(), caller="schedule").call("morning", ME)
    later = harness(tmp_path, claude(), caller="schedule", day=4, stars=125).call("morning", ME)
    assert "Stars: 125 (+5)" in later.data["summary"]
