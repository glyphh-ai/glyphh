"""Remote bots: a host (rrotor's glyphh-bot, Glyphh's cloud) holds a bot's package and state; a go runs it once, its
tools called over HTTP at the host (HttpProgram), and what it left goes over the wire as rrotor's Result
(RunResult.to_result, from_result). Ada, Claude and the host are fakes: no network."""

from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

import pytest

from conftest import FakeAda, FakeClaude
from glyphh.bots import Bot, BotError, Claude, HttpProgram, RunResult, ToolError
from glyphh.bots.remote import STATE, _post, go, output_of, pack_state, write_package

SPEC = {
    "name": "worth",
    "layers": [{"name": "d", "segments": [{"name": "s", "roles": [
        {"name": "n", "numeric_config": {"min_value": 0, "max_value": 50, "bin_width": 1}},
        {"name": "run", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"ask_below": 0.7},
}

AGENT = "---\nname: lister\ndescription: Sums up\n---\n\nYou are Lister.\n"


def package(**over: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "slug": "lister",
        "name": "Lister",
        "agent": "agent.md",
        "touches": "sends",
        "gates": {"worth": {"case": {"d": {"s": {"n": "$fetch.count", "run": "x"}}}, "outcomes": ["send", "skip"],
                            "question": "Worth it?", "spec": SPEC}},
        "loop": [
            {"id": "fetch", "run": "inbox", "input": {"box": "$input.box"}},
            {"id": "worth", "gate": "worth", "on": {"send": "sum", "skip": "end"}},
            {"id": "sum", "agent": "Sum up: $fetch", "skill": "lines"},
            {"id": "post", "run": "slack_post", "input": {"text": "$sum"}, "approval": "post it"},
        ],
    }
    spec.update(over)
    return {"bot.json": spec, "agent.md": AGENT, "skills/lines/SKILL.md": "---\nname: lines\n---\n\nOne line each.\n"}


class FakeHost:
    """The host's tool URL: each request kept, answered from `answers` by tool."""

    def __init__(self, answers: Dict[str, Any]) -> None:
        self.answers = answers
        self.asked: List[Tuple[urllib.request.Request, Dict[str, Any], float]] = []

    def __call__(self, req: urllib.request.Request, timeout: float) -> Any:
        body = json.loads(req.data)  # type: ignore[arg-type]
        self.asked.append((req, body, timeout))
        return self.answers[body["tool"]]


def host() -> FakeHost:
    return FakeHost({"inbox": {"result": {"count": 3, "items": ["a", "b", "c"]}}, "slack_post": {"result": {"ok": True}}})


def test_http_program_posts_each_tool_with_its_bearer_and_answers_its_result():
    h = host()
    program = HttpProgram("https://api.glyphh.ai/v1/bots/runs/r1/tool", "tok_secret", post=h)
    ctx = type("C", (), {"run_id": "run-1"})()
    assert program.inbox(ctx, {"box": "in"}) == {"count": 3, "items": ["a", "b", "c"]}
    req, body, timeout = h.asked[0]
    assert req.full_url == "https://api.glyphh.ai/v1/bots/runs/r1/tool" and req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer tok_secret" and req.get_header("Content-type") == "application/json"
    assert body == {"tool": "inbox", "input": {"box": "in"}, "run_id": "run-1"} and timeout == 130.0
    program.slack_post(ctx)
    assert h.asked[1][1]["input"] is None
    program.slack_post(ctx, "rung", {"x": 1})  # a ladder's try gives several inputs: sent as a list
    assert h.asked[2][1]["input"] == ["rung", {"x": 1}]
    assert "tok_secret" not in repr(program)
    with pytest.raises(AttributeError):
        program._private  # noqa: B018
    with pytest.raises(BotError):
        HttpProgram("ftp://x", "t")


def test_http_program_names_its_tools_and_fails_a_step_on_the_hosts_error():
    program = HttpProgram("https://h/t", "t", tools=["inbox"], post=FakeHost({
        "inbox": {"error": {"message": "the connection is gone"}}}))
    assert callable(program.inbox)
    with pytest.raises(AttributeError):
        program.slack_post  # noqa: B018
    with pytest.raises(ToolError, match="inbox: the connection is gone"):
        program.call("inbox", {})
    for answer, said in (([1], "not a JSON object"), ({"ok": 1}, "has no result"), ({"error": "no"}, "inbox: no")):
        with pytest.raises(ToolError, match=said):
            HttpProgram("https://h/t", "t", post=FakeHost({"inbox": answer})).call("inbox")


def test_the_real_post_reads_errors_the_host_answers(monkeypatch):
    req = urllib.request.Request("https://h/t", data=b"{}")

    def answering(body: bytes, code: int = 400):
        def opened(r: Any, timeout: float) -> Any:
            raise urllib.error.HTTPError("https://h/t", code, "Bad", {}, io.BytesIO(body))  # type: ignore[arg-type]
        return opened

    monkeypatch.setattr(urllib.request, "urlopen", answering(b'{"error": "not in scope"}'))
    assert _post(req, 1.0) == {"error": "not in scope"}
    monkeypatch.setattr(urllib.request, "urlopen", answering(b"<html>", 502))
    with pytest.raises(ToolError, match="the host answered 502 Bad"):
        _post(req, 1.0)

    def unreachable(r: Any, timeout: float) -> Any:
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(ToolError, match="could not be reached: refused"):
        _post(req, 1.0)

    class Res(io.BytesIO):
        def __enter__(self) -> "Res":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda r, timeout: Res(b'{"result": 1}'))
    assert _post(req, 1.0) == {"result": 1}


def test_a_package_is_written_without_code_and_its_state_carried(tmp_path):
    folder = write_package(tmp_path / "b", package(), base64.b64encode(b"sqlite bytes").decode())
    assert json.loads((folder / "bot.json").read_text())["slug"] == "lister"
    assert (folder / "skills" / "lines" / "SKILL.md").exists() and (folder / STATE).read_bytes() == b"sqlite bytes"
    assert pack_state(folder) == base64.b64encode(b"sqlite bytes").decode()
    assert pack_state(tmp_path) is None
    text = write_package(tmp_path / "t", {"bot.json": "{}", "agent.md": "x"})
    assert (text / "bot.json").read_text() == "{}"
    for files, said in (
        ({"agent.md": "x"}, "bot.json among them"),
        ({"bot.json": {}, "../x": "y"}, "not a path inside"),
        ({"bot.json": {}, "/etc/x": "y"}, "not a path inside"),
        ({"bot.json": {}, STATE: "y"}, "not a path inside"),
        ({"bot.json": {}, "program.py": "import os"}, "carries no code"),
        ({"bot.json": {}, "agent.md": 3}, "is text"),
    ):
        with pytest.raises(BotError, match=said):
            write_package(tmp_path / "bad", files)
    with pytest.raises(BotError, match="not base64"):
        write_package(tmp_path / "bad", {"bot.json": {}}, "not base64!")


def test_a_go_runs_from_the_first_step_and_stops_at_a_question_with_its_state(fake_claude: FakeClaude):
    ada, h = FakeAda(), host()
    program = HttpProgram("https://h/t", "t", post=h)
    left = go(package(), ada=ada, claude=Claude(run=fake_claude), program=program, given={"box": "in"})
    assert left.status == "needs_input" and left.step == "worth" and left.approval is None
    assert left.question.startswith("Worth it?") and left.options == ["send", "skip"]
    assert h.asked[0][1]["input"] == {"box": "in"} and left.state and left.output is None
    assert left.tokens == {"input_tokens": 0, "output_tokens": 0}
    assert sorted(ada.specs) == ["bot-lister-gate-worth", "bot-lister-instructions", "bot-lister-memory",
                                 "bot-lister-personality"]

    on = go(package(), ada=ada, claude=Claude(run=fake_claude), program=program, state=left.state, answer="send")
    assert on.status == "needs_input" and on.approval is True and on.step == "post" and on.options == ["yes", "no"]
    assert ada.cases["bot-lister-gate-worth"][0][1] == "send"

    fake_claude.answers = []
    done = go(package(), ada=ada, claude=Claude(run=fake_claude), program=program, state=on.state, answer="yes")
    assert done.status == "done" and done.run_id == left.run_id
    assert h.asked[-1][1] == {"tool": "slack_post", "input": {"text": "an answer"}, "run_id": left.run_id}
    assert done.output == json.dumps({"ok": True})
    assert len(ada.specs) == 4  # installed once for the shape of its gates and seed


def test_a_go_whose_package_is_wrong_says_so(fake_claude: FakeClaude):
    with pytest.raises(BotError, match="not JSON"):
        go({"bot.json": "{", "agent.md": AGENT}, ada=FakeAda(), claude=Claude(run=fake_claude), program=host())
    with pytest.raises(BotError):
        go({"bot.json": [], "agent.md": AGENT}, ada=FakeAda(), claude=Claude(run=fake_claude), program=host())


def test_a_result_goes_over_the_wire_and_comes_back():
    asking = RunResult("lister", "r1", "needs_input", "Worth it?", "Worth it? Which?", ["send", "skip"], step="worth",
                       state="c3RhdGU=", tokens={"input_tokens": 5, "output_tokens": 2})
    wire = asking.to_result()
    assert wire["status"] == "needs_input" and wire["prompt"] == "Worth it? Which?" and wire["step"] == "worth"
    assert wire["data"]["options"] == ["send", "skip"] and wire["data"]["schema"] is None
    assert wire["data"]["state"] == "c3RhdGU=" and json.loads(json.dumps(wire)) == wire
    assert RunResult.from_result(wire) == asking

    approval = RunResult("lister", "r1", "needs_input", "post: post it. Yes?", "post: post it. Yes?", ["yes", "no"],
                         step="post", approval=True)
    wire = approval.to_result()
    assert wire["status"] == "needs_approval" and wire["step"] == "post" and wire["prompt"] == "post: post it. Yes?"
    assert RunResult.from_result(wire) == RunResult(**{**approval.__dict__,
                                                       "tokens": {"input_tokens": 0, "output_tokens": 0}})
    bare = RunResult.from_result({"status": "needs_approval", "data": None, "step": "s", "prompt": "Go?"})
    assert (bare.status, bare.options, bare.question, bare.approval) == ("needs_input", ["yes", "no"], "Go?", True)

    done = RunResult("lister", "r1", "done", output="the sum", data={"sum": "the sum"})
    wire = done.to_result()
    assert (wire["status"], wire["step"], wire["prompt"], wire["data"]["output"]) == ("done", None, None, "the sum")
    assert RunResult.from_result(wire).data == {"sum": "the sum"}
    skipped = RunResult("lister", "", "skipped", "quiet hours")
    assert skipped.to_result()["status"] == "done" and RunResult.from_result(skipped.to_result()).status == "skipped"

    failed = RunResult("lister", "r1", "failed", "sum: Claude failed", state="eA==")
    wire = failed.to_result()
    assert (wire["status"], wire["step"]) == ("failed", "bot") and wire["data"]["reason"] == "sum: Claude failed"
    back = RunResult.from_result(wire)
    assert (back.status, back.reason, back.state) == ("failed", "sum: Claude failed", "eA==")


@pytest.mark.parametrize(("result", "said"), [
    ({"status": "failed", "data": {"reason": "No such run.", "code": "E_RUN_MISSING"}, "step": "continue"},
     "the run failed (E_RUN_MISSING): No such run."),
    ({"status": "cancelled", "data": None, "step": "cancel", "prompt": None}, "the run was cancelled"),
    ({"status": "expired", "data": {"reason": "15 minutes"}}, "the run expired: nobody answered in time: 15 minutes"),
    ({"status": "odd"}, "the run ended odd"),
])
def test_a_result_the_bot_never_reached_is_failed_saying_what_rrotor_said(result, said):
    got = RunResult.from_result(result)
    assert (got.status, got.reason, got.bot) == ("failed", said, "")


def test_output_is_the_last_steps_data_that_has_any(tmp_path):
    bot = Bot.load(write_package(tmp_path / "b", package()), program=HttpProgram("https://h/t", "t", post=host()))
    ran = RunResult("lister", "r", "done", data={"fetch": {"n": 1}, "sum": "x" * 60_000})
    assert output_of(bot, ran) == "x" * 50_000
    assert output_of(bot, RunResult("lister", "r", "done", data={"fetch": {"n": 1}})) == '{"n": 1}'
    assert output_of(bot, RunResult("lister", "r", "done")) == ""
