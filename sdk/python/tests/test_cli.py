"""The `glyphh` command and its sign-in: the device flow as the plugin runs it (its requests, its polling, the install
kept 0600 in ~/.glyphh/install.json), the SDK reading that sign-in, and each command printing the API's own answer."""

from __future__ import annotations

import json
import stat
from typing import Any, List

import pytest

import glyphh.client
import glyphh.signin
from glyphh import cli
from glyphh.errors import AdaError
from glyphh.signin import Install, SignIn, read_install, write_install


class Server:
    """The Glyphh server's device flow and /v1/me, answered in turn."""

    def __init__(self, *answers: Any) -> None:
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, body, bearer):
        self.calls.append((method, url, body, bearer))
        status, answer = self.answers.pop(0)
        return status, json.dumps(answer)


CODE = {
    "device_code": "dc1",
    "user_code": "ABCD-EFGH",
    "verification_uri": "https://api.glyphh.ai/v1/device",
    "verification_uri_complete": "https://api.glyphh.ai/v1/device?code=ABCD-EFGH",
    "interval": 5,
    "expires_in": 600,
}


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("GLYPHH_API_KEY", "GLYPHH_RUNTIME_KEY", "GLYPHH_SERVER_URL", "GLYPHH_ADA_URL"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def clock(monkeypatch):
    now, slept = [0.0], []

    def sleep(s):
        slept.append(s)
        now[0] += s

    monkeypatch.setattr(glyphh.signin, "_sleep", sleep)
    monkeypatch.setattr(glyphh.signin, "_now", lambda: now[0])
    return slept


def flow(server: Server, home) -> SignIn:
    return SignIn(http=server, path=home / ".glyphh" / "install.json", machine=lambda: "m" * 64, name="mac", version="t")


def test_a_sign_in_is_the_plugins_device_flow_and_keeps_the_install(home, clock):
    server = Server(
        (200, CODE),
        (400, {"error": "authorization_pending"}),
        (400, {"error": {"code": "slow_down"}}),
        (200, {"access_token": "glyphh_it_1", "install_id": "i1"}),
        (200, {"user": {"email": "ada@example.com"}}),
    )
    f = flow(server, home)
    p = f.start()
    assert (p.user_code, p.verification_uri_complete) == ("ABCD-EFGH", CODE["verification_uri_complete"])
    assert server.calls[0] == (
        "POST",
        "https://api.glyphh.ai/v1/device/code",
        {"name": "mac", "surface": "cli", "mod_version": "t", "machine_id": "m" * 64},
        None,
    )
    assert f.wait(p) == "ada@example.com"
    assert clock == [5, 5, 10]  # the interval, and five more after slow_down
    assert [c[2] for c in server.calls[1:4]] == [{"device_code": "dc1"}] * 3
    assert server.calls[4][:2] == ("GET", "https://api.glyphh.ai/v1/me") and server.calls[4][3] == "glyphh_it_1"
    path = home / ".glyphh" / "install.json"
    assert read_install(path) == Install("i1", "glyphh_it_1")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and json.loads(path.read_text())["install_id"] == "i1"


@pytest.mark.parametrize(("refusal", "code"), [("expired_token", "E_EXPIRED"), ("access_denied", "E_DENIED"), ("nope", "E_SERVER")])
def test_a_sign_in_that_ends_unapproved_says_why_and_keeps_nothing(home, clock, refusal, code):
    f = flow(Server((200, CODE), (400, {"error": refusal})), home)
    with pytest.raises(AdaError) as caught:
        f.wait(f.start())
    assert caught.value.code == code and read_install(f.path) is None


def test_a_code_left_too_long_expires_here_too(home, clock):
    f = flow(Server((200, {**CODE, "expires_in": 12}), (400, {"error": "authorization_pending"}), (400, {"error": "authorization_pending"})), home)
    with pytest.raises(AdaError) as caught:
        f.wait(f.start())
    assert caught.value.code == "E_EXPIRED" and clock == [5, 5, 5]


def test_whoami_and_sign_out(home):
    f = flow(Server(), home)
    assert f.whoami() is None and f.sign_out() is False  # nothing asked of the server
    write_install(Install("i1", "tok"), f.path)
    f._http = Server((200, {"email": "ada@example.com"}), (401, {"error": {"code": "E_AUTH"}}), (204, {}))
    assert f.whoami() == "ada@example.com" and f.whoami() is None
    assert f.sign_out() is True and read_install(f.path) is None
    assert f._http.calls[-1] == ("POST", "https://api.glyphh.ai/v1/sign-out", None, "tok")


def test_the_machine_id_is_the_plugins(monkeypatch, home):
    monkeypatch.setattr(glyphh.signin, "_hardware_id", lambda system: "HW-UUID")
    import hashlib

    assert glyphh.signin.machine_id(home) == hashlib.sha256(b"glyphh:HW-UUID").hexdigest()
    monkeypatch.setattr(glyphh.signin, "_hardware_id", lambda system: None)
    monkeypatch.setattr(glyphh.signin, "_primary_mac", lambda system: None)
    first = glyphh.signin.machine_id(home)
    assert glyphh.signin.machine_id(home) == first  # the random id is kept once in ~/.glyphh/machine.json
    assert (home / ".glyphh" / "machine.json").exists()


def test_the_server_url_moves_as_the_plugins_does(monkeypatch):
    monkeypatch.setenv("GLYPHH_SERVER_URL", "http://localhost:8000/ ")
    assert glyphh.signin.server_url() == "http://localhost:8000"


# the command


class Ada:
    """The Ada API, answered in turn, behind the real client."""

    def __init__(self, *answers: Any) -> None:
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers, raw):
        self.calls.append((method, url, headers, None if raw is None else json.loads(raw)))
        status, body = self.answers.pop(0)
        return status, json.dumps(body).encode()


@pytest.fixture
def api(monkeypatch, home):
    write_install(Install("i1", "glyphh_it_1"))
    holder: List[Ada] = []

    def use(*answers):
        holder.append(Ada(*answers))
        return holder[-1]

    real = glyphh.client.Ada.__init__

    def init(self, url=None, key=None, **kw):
        real(self, url, key, transport=holder[-1], retry_deadline=0)

    monkeypatch.setattr(glyphh.client.Ada, "__init__", init)
    return use


DECISION = {"outcome": "refund", "probabilities": {"refund": 0.9}, "expected_cost": 1.2, "ask": False, "receipts": [], "model": "tickets", "version": 3}


def test_decide_prints_the_apis_answer_on_the_sign_in(api, capsys, tmp_path):
    fake = api((200, DECISION))
    case = tmp_path / "case.json"
    case.write_text('{"ticket": {"text": "charged twice"}}')
    assert cli.main(["decide", "tickets", f"@{case}", "--outputs", "kind,refund", "--facts"]) == 0
    assert json.loads(capsys.readouterr().out) == DECISION
    method, url, headers, body = fake.calls[0]
    assert (method, url, headers["authorization"]) == ("POST", "https://ada.glyphh.ai/v1/decide", "Bearer glyphh_it_1")
    assert body == {"model": "tickets", "data": {"ticket": {"text": "charged twice"}}, "outputs": ["kind", "refund"], "include": ["facts"]}


def test_record_and_record_many(api, capsys, tmp_path):
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
    api((404, {"error": {"code": "E_MODEL_MISSING", "message": "No model tickets.", "trace_id": "t"}}))
    assert cli.main(["model", "tickets"]) == 1
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["code"] == "E_MODEL_MISSING" and err["message"] == "No model tickets."


def test_delete_asks_for_the_name_again(api, capsys):
    fake = api()
    assert cli.main(["delete", "tickets", "--confirm", "ticket"]) == 1
    assert "--confirm tickets" in json.loads(capsys.readouterr().err)["error"]["message"] and fake.calls == []


def test_no_sign_in_and_no_key_says_how(home, capsys):
    assert cli.main(["models"]) == 1
    assert "glyphh login" in json.loads(capsys.readouterr().err)["error"]["message"]


def test_login_when_signed_in_already_starts_nothing(monkeypatch, home, capsys):
    monkeypatch.setattr(SignIn, "whoami", lambda self: "ada@example.com")
    monkeypatch.setattr(SignIn, "start", lambda self: pytest.fail("a new sign-in"))
    assert cli.main(["login"]) == 0
    assert json.loads(capsys.readouterr().out) == {"signed_in": True, "email": "ada@example.com"}


def test_a_bad_json_argument_is_a_usage_mistake(home, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["decide", "tickets", "{not json"])
    assert caught.value.code == 2 and "not JSON" in capsys.readouterr().err
