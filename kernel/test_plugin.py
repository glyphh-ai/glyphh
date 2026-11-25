"""Hook behavior tests for the Ada plugin. Each hook is run as a
subprocess with synthetic stdin, the way Claude Code runs it."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# the plugin's hooks and server read the SQLite files themselves, in their own processes
pytestmark = pytest.mark.sqlite_only

REPO = Path(__file__).parent
HOOKS = REPO / "plugin" / "hooks"


def run_hook(name: str, payload: dict, home: Path):
    """Run a hook with GLYPHH_HOME=home, so its memory is home/ada."""
    env = {**os.environ, "GLYPHH_HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload), capture_output=True, text=True, env=env)


@pytest.fixture()
def workspace(tmp_path):
    """A GLYPHH_HOME with a small real memory, plus a unique session id."""
    sys.path.insert(0, str(REPO))
    from glyphh_kernel import Space
    mem = tmp_path / "ada"
    with Space(author="test-agent", path=str(mem / "wins.db")) as wins:
        wins.record({"task": "deploy_service", "constraint": "canary_required"},
                    "canary_then_full_rollout")
    with Space(author="test-agent", path=str(mem / "vetoes.db")) as vetoes:
        vetoes.record({"task": "deploy_service", "constraint": "canary_required"},
                      "big_bang_deploy")
    session = f"pytest-{tmp_path.name}"
    yield tmp_path, session
    import tempfile
    shutil.rmtree(Path(tempfile.gettempdir()) / "ada-hooks",
                  ignore_errors=True)


def test_session_start_injects_state(workspace):
    home, session = workspace
    result = run_hook("session_start.py",
                      {"session_id": session, "cwd": str(home)}, home)
    assert result.returncode == 0
    assert "1 wins, 1 vetoes" in result.stdout
    assert "deploy_service" in result.stdout
    assert "big_bang_deploy" in result.stdout


def test_session_start_ignores_cwd(workspace, tmp_path_factory):
    """The memory is always on: any home sees the same store."""
    home, session = workspace
    elsewhere = tmp_path_factory.mktemp("unrelated")
    result = run_hook("session_start.py",
                      {"session_id": session, "cwd": str(elsewhere)}, home)
    assert result.returncode == 0
    assert "1 wins, 1 vetoes" in result.stdout


def test_session_start_empty_memory(tmp_path):
    result = run_hook("session_start.py",
                      {"session_id": "x", "cwd": str(tmp_path)}, tmp_path)
    assert result.returncode == 0
    assert "0 wins, 0 vetoes" in result.stdout


def test_user_prompt_surfaces_relevant_precedent(workspace):
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "ok let's deploy the service to prod, the canary env is ready"}, home)
    assert result.returncode == 0
    assert "canary_then_full_rollout" in result.stdout
    assert "VETOED: big_bang_deploy" in result.stdout


def test_user_prompt_silent_on_unrelated(workspace):
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "write a haiku about autumn leaves"}, home)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_gate_blocks_once_then_passes(workspace):
    home, session = workspace
    run_hook("session_start.py", {"session_id": session, "cwd": str(home)}, home)
    first = run_hook("stop_gate.py",
                     {"session_id": session, "stop_hook_active": False}, home)
    assert first.returncode == 2
    assert "record" in first.stderr
    second = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": False}, home)
    assert second.returncode == 0


def test_stop_gate_passes_when_something_was_recorded(workspace):
    home, session = workspace
    run_hook("session_start.py", {"session_id": session, "cwd": str(home)}, home)
    from glyphh_kernel import Space
    with Space(author="test-agent", path=str(home / "ada" / "wins.db")) as wins:
        wins.record({"task": "deploy_service", "constraint": "no_canary"},
                    "staged_rollout")
    result = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": False}, home)
    assert result.returncode == 0


def test_stop_gate_never_loops(workspace):
    home, session = workspace
    result = run_hook("stop_gate.py",
                      {"session_id": session, "stop_hook_active": True}, home)
    assert result.returncode == 0


def test_plugin_kernel_copy_in_sync():
    assert (REPO / "plugin" / "glyphh_kernel.py").read_text() == \
        (REPO / "glyphh_kernel.py").read_text()


def test_plugin_skill_copy_in_sync():
    assert (REPO / "plugin" / "skills" / "glyphh-think" / "SKILL.md").read_text() == \
        (REPO / ".claude" / "skills" / "glyphh-think" / "SKILL.md").read_text()


def test_user_prompt_matches_morphology_and_typos(workspace):
    """'deploying'/'deploy' and suffix typos must still surface the
    precedent — the miss that motivated prefix matching was a prompt
    saying 'fish'/'Christ' against stored 'fishing'/'chris'."""
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "we're deploying the servicey thing, canary env is up"}, home)
    assert result.returncode == 0
    assert "canary_then_full_rollout" in result.stdout


def test_user_prompt_outcome_tokens_ring_the_bell(workspace):
    """A prompt mentioning only the OUTCOME vocabulary (not the
    situation's) still surfaces the precedent."""
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "maybe a canary rollout then going full?"}, home)
    assert "canary_then_full_rollout" in result.stdout


def test_user_prompt_veto_doorbell(workspace):
    """Contemplating a vetoed approach surfaces the veto."""
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "let's do a big bang deploy of the service"}, home)
    assert "VETOED: big_bang_deploy" in result.stdout


def test_user_prompt_typo_tolerance(workspace):
    """Edit-distance-1 including transpositions."""
    home, session = workspace
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "time to depoly the sevrice now"}, home)
    assert "canary_then_full_rollout" in result.stdout


def test_user_prompt_aliases(workspace):
    """aliases.json maps surface forms to canonical tokens."""
    home, session = workspace
    (home / "ada" / "aliases.json").write_text(
        json.dumps({"ship": ["deploy"], "svc": ["service"]}))
    result = run_hook("user_prompt.py", {
        "session_id": session, "cwd": str(home),
        "prompt": "ok lets ship the svc"}, home)
    assert "canary_then_full_rollout" in result.stdout
