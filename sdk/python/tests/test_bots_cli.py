"""`glyphh bot ...`: each command's answer is JSON on stdout, a refusal JSON on stderr with exit 1, a failed run exit 1;
with no terminal a question stops the run until `glyphh bot continue`."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, List

import pytest

import glyphh.bots.cli as bots_cli
from conftest import FakeAda, FakeClaude, digest_spec, write_bot
from glyphh import cli
from glyphh.bots import Claude


@pytest.fixture
def glyphh_bot(monkeypatch, fake_ada: FakeAda, fake_claude: FakeClaude, bots_home: Path, capsys):
    monkeypatch.setattr(bots_cli, "connect", lambda root: fake_ada)
    monkeypatch.setattr(bots_cli, "Claude", lambda: Claude(run=fake_claude))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    def run(*argv: str, code: int = 0) -> Any:
        got = cli.main(["bot", *argv, "-q"])
        out = capsys.readouterr()
        assert got == code, out.err
        return json.loads(out.out if code == 0 or out.out else out.err)

    return run


def test_install_run_continue_and_correct_from_the_command(glyphh_bot, bot_folder, fake_ada, monkeypatch):
    assert glyphh_bot("init")["made"]
    assert glyphh_bot("check", str(bot_folder))["models"][0] == "bot-digest-gate-worth"
    assert glyphh_bot("install", str(bot_folder), "--job", "sum up the items")["trust"] == "ask_all"
    monkeypatch.setattr("glyphh.bots.runner._urlopen", lambda req, timeout: {"items": [{"title": "one"}]})
    asked = glyphh_bot("run", "digest")
    assert asked["status"] == "needs_input" and asked["options"] == ["send", "skip"]
    assert glyphh_bot("continue", "digest", "send")["options"] == ["yes", "no"]
    done = glyphh_bot("continue", "digest", "yes")
    assert done["status"] == "done" and done["run_id"] == asked["run_id"]
    fixed = glyphh_bot("wrong", "digest", asked["run_id"], "skip", "--gate", "worth")
    assert fixed["now"] == "skip" and fake_ada.outcomes("bot-digest-gate-worth") == ["send", "skip"]
    assert glyphh_bot("status", "digest")["runs"][0]["status"] == "done"
    assert glyphh_bot("status")["bots"][0]["job"] == "sum up the items"


def test_review_verdict_and_new_from_the_command(glyphh_bot, bot_folder):
    glyphh_bot("install", str(bot_folder))
    asked = glyphh_bot("review")
    assert [c["outcome"] for c in asked] == [None, None]
    got = glyphh_bot("review", "--answer", "digest.trust_bot=ask_outward", "digest.keep_bot=keep")
    assert [c["outcome"] for c in got] == ["ask_outward", "keep"]
    assert glyphh_bot("verdict", "digest", "keep", "fix") == {"bot": "digest", "keep": "fix", "by": "person"}
    err = glyphh_bot("verdict", "digest", "trust", "fix", code=1)
    assert "a trust verdict is one of" in err["error"]["message"]
    err = glyphh_bot("review", "--answer", "nonsense", code=1)
    assert err["error"]["code"] == "E_BOT"
    new = glyphh_bot("new", "each morning, sum up the new issues")
    assert new["status"] == "needs_input" and new["gate"] == "make_bot"


def test_a_failed_run_exits_1_and_a_bad_package_says_each_problem(glyphh_bot, tmp_path):
    folder = write_bot(tmp_path / "x" / "digest", digest_spec(loop=[{"id": "boom", "run": "boom"}], touches="read_only"))
    glyphh_bot("install", str(folder))
    assert glyphh_bot("run", "digest", "--routine", code=1)["status"] == "failed"
    bad = write_bot(tmp_path / "y" / "digest", digest_spec(name=""))
    err = glyphh_bot("check", str(bad), code=1)
    assert err["error"]["code"] == "E_BOT" and "name is missing" in err["error"]["problems"]


def test_routine_installs_through_the_routine_module(glyphh_bot, bot_folder, monkeypatch):
    seen: List[Any] = []
    monkeypatch.setattr(bots_cli, "install_routine", lambda bot, remove: seen.append((bot.slug, remove)) or {"ok": 1})
    glyphh_bot("install", str(bot_folder))
    assert glyphh_bot("routine", "digest", "--remove") == {"ok": 1} and seen == [("digest", True)]


def test_the_terminal_is_asked_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("send\n"))
    assert bots_cli._terminal_ask("Worth it?", ["send", "skip"]) == "send\n"
    assert "? Worth it? [send/skip]" in capsys.readouterr().err
    with pytest.raises(bots_cli.BotError, match="terminal closed"):
        bots_cli._terminal_ask("Again?", ["yes"])
    capsys.readouterr()
    bots_cli._echo(False)("a line")
    assert capsys.readouterr().err == "  a line\n" and bots_cli._echo(True) is None
