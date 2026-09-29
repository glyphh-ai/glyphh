"""Hook behavior tests for the glyphh plugin. Each hook is run as a
subprocess with synthetic stdin, the way Claude Code runs it."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent
HOOKS = REPO / "plugin" / "hooks"


def run_hook(name: str, payload: dict):
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload), capture_output=True, text=True)


@pytest.fixture()
def workspace(tmp_path):
    """A workspace with a small real memory, plus a unique session id."""
    sys.path.insert(0, str(REPO))
    from glyphh_kernel import Space
    mem = tmp_path / "dogfood"
    with Space(author="test-agent", path=str(mem / "wins.db")) as wins:
        wins.record({"task": "deploy_service", "constraint": "canary_required"},
                    "canary_then_full_rollout")
    with Space(author="test-agent", path=str(mem / "vetoes.db")) as vetoes:
        vetoes.record({"task": "deploy_service", "constraint": "canary_required"},
                      "big_bang_deploy")
    session = f"pytest-{tmp_path.name}"
    yield tmp_path, session
    shutil.rmtree("/tmp/glyphh-hooks", ignore_errors=True)


def test_session_start_injects_state(workspace):
    cwd, session = workspace
    result = run_hook("session_start.py",
                      {"session_id": session, "cwd": str(cwd)})
    assert result.returncode == 0
    assert "1 wins, 1 vetoes" in result.stdout
    assert "deploy_service" in result.stdout
    assert "big_bang_deploy" in result.stdout


def test_session_start_silent_without_glyphh(tmp_path):
    result = run_hook("session_start.py",
                      {"session_id": "x", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_user_prompt_surfaces_relevant_precedent(workspace):
    cwd, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(cwd),
        "prompt": "ok let's deploy the service to prod, the canary env is ready"})
    assert result.returncode == 0
    assert "canary_then_full_rollout" in result.stdout
    assert "vetoed: big_bang_deploy" in result.stdout


def test_user_prompt_silent_on_unrelated(workspace):
    cwd, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(cwd),
        "prompt": "write a haiku about autumn leaves"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_gate_blocks_once_then_passes(workspace):
    cwd, session = workspace
    run_hook("session_start.py", {"session_id": session, "cwd": str(cwd)})
    first = run_hook("stop_gate.py",
                     {"session_id": session, "stop_hook_active": False})
    assert first.returncode == 2
    assert "record" in first.stderr
    second = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": False})
    assert second.returncode == 0


def test_stop_gate_passes_when_something_was_recorded(workspace):
    cwd, session = workspace
    run_hook("session_start.py", {"session_id": session, "cwd": str(cwd)})
    from glyphh_kernel import Space
    with Space(author="test-agent", path=str(cwd / "dogfood" / "wins.db")) as wins:
        wins.record({"task": "deploy_service", "constraint": "no_canary"},
                    "staged_rollout")
    result = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": False})
    assert result.returncode == 0


def test_stop_gate_never_loops(workspace):
    _, session = workspace
    result = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": True})
    assert result.returncode == 0


def test_plugin_kernel_copy_in_sync():
    assert (REPO / "plugin" / "glyphh_kernel.py").read_text() == \
        (REPO / "glyphh_kernel.py").read_text()


def test_plugin_skill_copy_in_sync():
    assert (REPO / "plugin" / "skills" / "glyphh-memory" / "SKILL.md").read_text() == \
        (REPO / ".claude" / "skills" / "glyphh-memory" / "SKILL.md").read_text()
