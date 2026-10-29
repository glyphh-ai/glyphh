"""The `glyphh` command: an API key kept 0600 in ~/.glyphh/credentials.json by `glyphh login` (checked against Ada
first), GLYPHH_API_KEY winning over it, and each command printing the API's own answer."""

from __future__ import annotations

import io
import json
import stat
from typing import Any, List

import pytest

import glyphh.client
from glyphh import cli
from glyphh.credentials import credentials_path, read_key, save_key

USAGE = {"plan": "Free", "month": "2026-10", "resets_at": "2026-11-01", "models": 1, "precedents": {"used": 0, "max": 1000}, "requests": {"used": 3, "max": 5000, "over": 0, "overage": False}, "requests_per_second": 5}


class Api:
    """The Ada API, answered in turn, behind the real client."""

    def __init__(self, *answers: Any) -> None:
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers, raw):
        self.calls.append((method, url, headers, None if raw is None else json.loads(raw)))
        status, body = self.answers.pop(0)
        return status, json.dumps(body).encode()


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("GLYPHH_API_KEY", "GLYPHH_RUNTIME_KEY", "GLYPHH_ADA_URL", "GLYPHH_RUNTIME_URL"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def api(monkeypatch, home):
    holder: List[Api] = []

    def use(*answers):
        holder.append(Api(*answers))
        return holder[-1]

    real = glyphh.client.Ada.__init__

    def init(self, url=None, key=None, **kw):
        real(self, url, key, transport=holder[-1], retry_deadline=0)

    monkeypatch.setattr(glyphh.client.Ada, "__init__", init)
    return use


def test_login_checks_the_key_then_keeps_it_0600(api, monkeypatch, capsys):
    fake = api((200, USAGE))
    monkeypatch.setattr("getpass.getpass", lambda prompt: "glyphh_ak_secret1234\n")
    assert cli.main(["login"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"logged_in": True, "key": "glyphh_ak_…1234", "plan": "Free", "kept": str(credentials_path())}
    assert fake.calls[0][1].endswith("/v1/usage") and fake.calls[0][2]["authorization"] == "Bearer glyphh_ak_secret1234"
    assert read_key() == "glyphh_ak_secret1234" and stat.S_IMODE(credentials_path().stat().st_mode) == 0o600


def test_a_key_ada_refuses_is_never_kept(api, monkeypatch, capsys):
    api((401, {"error": {"code": "E_AUTH", "message": "That key is not valid."}}))
    monkeypatch.setattr("sys.stdin", io.StringIO("glyphh_ak_revoked\n"))
    assert cli.main(["login", "--key-stdin"]) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "E_AUTH" and read_key() is None


def test_login_refuses_what_is_not_a_key(api, monkeypatch, capsys):
    fake = api()
    monkeypatch.setattr("sys.stdin", io.StringIO("sk-something\n"))
    assert cli.main(["login", "--key-stdin"]) == 1
    assert "glyphh_ak_" in json.loads(capsys.readouterr().err)["error"]["message"] and fake.calls == []


def test_whoami_says_which_key_and_from_where_and_logout_forgets_it(api, monkeypatch, capsys):
    api()
    assert cli.main(["whoami"]) == 0 and json.loads(capsys.readouterr().out) == {"logged_in": False}
    save_key("glyphh_ak_keptabcd")
    api((200, USAGE))
    assert cli.main(["whoami"]) == 0
    assert json.loads(capsys.readouterr().out) == {"logged_in": True, "key": "glyphh_ak_…abcd", "from": str(credentials_path()), "plan": "Free"}
    monkeypatch.setenv("GLYPHH_API_KEY", "glyphh_ak_fromenv9")  # the environment wins
    fake = api((200, USAGE), (200, {"models": []}))
    assert cli.main(["whoami"]) == 0 and json.loads(capsys.readouterr().out)["from"] == "GLYPHH_API_KEY"
    assert cli.main(["models"]) == 0 and fake.calls[1][2]["authorization"] == "Bearer glyphh_ak_fromenv9"
    capsys.readouterr()
    assert cli.main(["logout"]) == 0 and json.loads(capsys.readouterr().out)["logged_out"] is True and read_key() is None
    assert cli.main(["logout"]) == 0 and json.loads(capsys.readouterr().out)["logged_out"] is False


DECISION = {"outcome": "refund", "probabilities": {"refund": 0.9}, "expected_cost": 1.2, "ask": False, "receipts": [], "model": "tickets", "version": 3}


def test_decide_prints_the_apis_answer_on_the_kept_key(api, capsys, tmp_path):
    save_key("glyphh_ak_kept")
    fake = api((200, DECISION))
    case = tmp_path / "case.json"
    case.write_text('{"ticket": {"text": "charged twice"}}')
    assert cli.main(["decide", "tickets", f"@{case}", "--outputs", "kind,refund", "--facts"]) == 0
    assert json.loads(capsys.readouterr().out) == DECISION
    method, url, headers, body = fake.calls[0]
    assert (method, url, headers["authorization"]) == ("POST", "https://ada.glyphh.ai/v1/decide", "Bearer glyphh_ak_kept")
    assert body == {"model": "tickets", "data": {"ticket": {"text": "charged twice"}}, "outputs": ["kind", "refund"], "include": ["facts"]}


def test_record_and_record_many(api, capsys, tmp_path):
    save_key("glyphh_ak_kept")
    done = {"run_id": "", "model": "tickets", "version": 1, "function": "record", "status": "done", "data": {"id": "p1", "precedents": 4}, "step": None, "prompt": None, "seconds": 0}
    fake = api((200, done), (200, {"ids": ["a", "b"], "added": 2, "replaced": 0, "precedents": 6}))
    assert cli.main(["record", "tickets", '{"a": 1}', "--outcome", "refund"]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == {"id": "p1", "precedents": 4}
    assert fake.calls[0][3]["inputs"] == {"data": {"a": 1}, "outcome": "refund"}
    cases = tmp_path / "cases.jsonl"
    cases.write_text('{"data": {"a": 1}, "outcome": "x"}\n\n{"data": {"a": 2}, "outcome": "y"}\n')
    assert cli.main(["record-many", "tickets", str(cases)]) == 0
    assert json.loads(capsys.readouterr().out)["added"] == 2 and len(fake.calls[1][3]["cases"]) == 2


def test_a_refusal_is_json_on_stderr_and_exit_1(api, capsys):
    save_key("glyphh_ak_kept")
    api((404, {"error": {"code": "E_MODEL_MISSING", "message": "No model tickets.", "trace_id": "t"}}))
    assert cli.main(["model", "tickets"]) == 1
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["code"] == "E_MODEL_MISSING" and err["message"] == "No model tickets."


def test_delete_asks_for_the_name_again(api, capsys):
    fake = api()
    assert cli.main(["delete", "tickets", "--confirm", "ticket"]) == 1
    assert "--confirm tickets" in json.loads(capsys.readouterr().err)["error"]["message"] and fake.calls == []


def test_no_key_says_how(home, capsys):
    assert cli.main(["models"]) == 1
    assert "glyphh login" in json.loads(capsys.readouterr().err)["error"]["message"]


def test_a_bad_json_argument_is_a_usage_mistake(home, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["decide", "tickets", "{not json"])
    assert caught.value.code == 2 and "not JSON" in capsys.readouterr().err
