"""open_issues through rrotor.testing: the page's function with gh answered by FakeCli and the token given to the
harness, no network, no sign-in. Needs rrotor 0.4.0's SDK (ctx.cli's env)."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from rrotor import CliResult
from rrotor.testing import FakeCli, Harness

HERE = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((HERE / "glyphh.json").read_text())
TOKEN = "ghp_test_token"


def program() -> ModuleType:
    spec = importlib.util.spec_from_file_location("open_issues_program", HERE / "program.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue(number: int, title: str, author: str = "someone", created: str = "2026-10-30T09:00:00Z") -> dict[str, Any]:
    return {"number": number, "title": title, "author": {"login": author}, "createdAt": created, "url": f"https://github.com/glyphh-ai/glyphh/issues/{number}"}


def gh(answer: Any) -> FakeCli:
    return FakeCli(answer, allow=["issue list *", "pr *"])


def harness(tmp_path: Path, cli: FakeCli, secrets: dict[str, str] | None = None) -> Harness:
    return Harness(
        program(),
        tmp_path,
        today=lambda: date(2026, 11, 2),
        clis={"gh": cli},
        secrets={"GH_TOKEN": TOKEN} if secrets is None else secrets,
        declared=MANIFEST["secrets"],
    )


def test_the_manifest_runs_as_the_app_with_gh_and_a_secret_and_the_page_goes_through_rrotor_js():
    assert MANIFEST["kind"] == "app" and MANIFEST["app"]["entry"] == "index.html"
    assert MANIFEST["app"]["run_as"] == "app" and MANIFEST["app"]["roles"] == []
    assert MANIFEST["app"]["functions"] == ["issues"] and set(MANIFEST["functions"]) == {"issues"}
    assert MANIFEST["clis"] == ["gh"] and MANIFEST["secrets"] == ["GH_TOKEN"] and "hosts" not in MANIFEST
    page = (HERE / "index.html").read_text()
    assert '<script src="/apps/_/rrotor.js"></script>' in page
    assert page.index("await rrotor.ready()") < page.index('rrotor.call("issues"')
    assert "fetch(" not in page and "GH_TOKEN" not in page
    # The key goes to gh for the one command, from the vault, never anywhere else.
    source = (HERE / "program.py").read_text()
    assert 'env={"GH_TOKEN": ctx.secrets["GH_TOKEN"]}' in source


def test_the_open_issues_are_listed_by_gh_with_the_token(tmp_path):
    cli = gh(json.dumps([issue(9, "Newer", "ann"), issue(7, "Older", created="2026-10-25T08:00:00Z")]))
    h = harness(tmp_path, cli)
    done = h.call("issues", {"limit": 20})
    assert done.status == "done"
    assert done.data == {
        "repo": "glyphh-ai/glyphh",
        "total": 2,
        "issues": [
            {"number": 9, "title": "Newer", "author": "ann", "opened": "2026-10-30", "url": "https://github.com/glyphh-ai/glyphh/issues/9"},
            {"number": 7, "title": "Older", "author": "someone", "opened": "2026-10-25", "url": "https://github.com/glyphh-ai/glyphh/issues/7"},
        ],
        "refreshed_at": "2026-11-02",
    }
    [(name, args, stdin, *rest)] = h.cli_calls
    assert name == "gh" and stdin is None
    assert args == ["issue", "list", "--repo", "glyphh-ai/glyphh", "--state", "open", "--limit", "20", "--json", "number,title,author,createdAt,url"]
    assert "listed" in str(h.logs[-1])


def test_limit_defaults_to_fifty_and_no_issues_is_an_empty_list(tmp_path):
    h = harness(tmp_path, gh("[]"))
    done = h.call("issues", {})
    assert done.data["issues"] == [] and done.data["total"] == 0
    assert h.cli_calls[0][1][7] == "50"


def test_gh_failing_is_a_failed_result_with_its_stderr(tmp_path):
    h = harness(tmp_path, gh(CliResult(1, "", "gh: Bad credentials (HTTP 401)\n")))
    failed = h.call("issues", {})
    assert (failed.status, failed.step) == ("failed", "list")
    assert "Bad credentials" in failed.data["reason"]


def test_without_the_secret_the_run_fails_naming_it_and_gh_never_runs(tmp_path):
    h = harness(tmp_path, gh("[]"), secrets={})
    failed = h.call("issues", {})
    assert failed.status == "failed" and "GH_TOKEN" in failed.data["reason"]
    assert h.cli_calls == []
