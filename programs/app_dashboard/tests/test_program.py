"""deploy_failures through rrotor.testing: the page's function with GitHub answered by FakeHttp, no network."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from rrotor.testing import FakeHttp, Harness

HERE = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((HERE / "glyphh.json").read_text())
RUNS = "https://api.github.com/repos/glyphh-ai/glyphh/actions/runs"


def program() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_failures_program", HERE / "program.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runs(*names: str) -> dict[str, Any]:
    return {"workflow_runs": [{"name": n, "conclusion": "failure"} for n in names]}


def harness(tmp_path: Path, http: FakeHttp) -> Harness:
    return Harness(program(), tmp_path, http=http, today=lambda: date(2026, 11, 1))


def test_the_manifest_is_an_app_whose_page_calls_its_one_function():
    assert MANIFEST["kind"] == "app" and MANIFEST["app"]["entry"] == "index.html"
    assert MANIFEST["app"]["functions"] == ["failures"] and set(MANIFEST["functions"]) == {"failures"}
    assert MANIFEST["app"]["roles"] == ["sre", "admin"] and MANIFEST["hosts"] == ["api.github.com"]
    page = (HERE / "index.html").read_text()
    assert "/apps/deploy_failures/call/failures" in page and "connector" not in page.lower().replace("never a connector", "")


def test_failures_are_counted_by_workflow_most_first(tmp_path):
    http = FakeHttp({RUNS: runs("deploy", "test", "deploy", "lint", "deploy")})
    done = harness(tmp_path, http).call("failures", {"since": "2026-10-25"})
    assert done.status == "done"
    assert done.data == {
        "since": "2026-10-25",
        "total": 5,
        "by_workflow": [{"workflow": "deploy", "failures": 3}, {"workflow": "test", "failures": 1}, {"workflow": "lint", "failures": 1}],
    }
    [(method, url, _)] = http.calls
    assert method == "GET" and url.startswith(RUNS) and "status=failure" in url and "created=%3E%3D2026-10-25" in url


def test_since_defaults_to_a_week_ago_and_no_runs_is_an_empty_count(tmp_path):
    http = FakeHttp({RUNS: {"workflow_runs": []}})
    done = harness(tmp_path, http).call("failures", {})
    assert done.data == {"since": "2026-10-25", "total": 0, "by_workflow": []}


def test_a_run_without_a_name_is_counted_as_unnamed(tmp_path):
    http = FakeHttp({RUNS: {"workflow_runs": [{"conclusion": "failure"}]}})
    assert harness(tmp_path, http).call("failures", {}).data["by_workflow"] == [{"workflow": "unnamed", "failures": 1}]
