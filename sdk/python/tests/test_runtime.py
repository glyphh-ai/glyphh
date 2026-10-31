"""The runtime client against a local rrotor's fixtures (contract/runtime-fixtures.json, written from rrotor's code):
every request as rrotor expects it (the paths, the bodies, the local token), every answer typed, every refusal its
typed RrotorError; reads sent again while rrotor is unreachable for a moment, writes never. No network: a fake
transport answers."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import validate

import glyphh
import glyphh.client
import glyphh.runtime
from glyphh import (
    AdaError,
    CliDeniedError,
    LocalOnlyError,
    ManifestError,
    NoHeadError,
    NotHeadError,
    ProgramMissingError,
    RrotorAuthError,
    RrotorError,
    RunStateError,
    Runtime,
    ScheduleMissingError,
)

ROOT = Path(__file__).parents[3]
CONTRACT = json.loads((ROOT / "contract" / "runtime.json").read_text())
FIXTURES = json.loads((ROOT / "contract" / "runtime-fixtures.json").read_text())
URL = "http://127.0.0.1:7777"
TOKEN = "local-token-test"


class Fake:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, headers, body):
        sent = body
        if body and headers.get("content-type") == "application/json":
            sent = json.loads(body)
        elif body:
            sent = body.decode()
        self.calls.append((method, url.removeprefix(URL), dict(headers), sent))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, content, *got = answer
        return (status, json.dumps(content).encode(), *got)


def case(name):
    return next(c for c in FIXTURES["cases"] if c["name"] == name)


def answered(name):
    c = case(name)
    return (c["response"]["status"], c["response"]["body"])


def runtime(*answers, **options):
    fake = Fake(*answers)
    return Runtime(URL + "/", TOKEN, transport=fake, **options), fake


def asked(fake, name, i=-1):
    """The request the client sent is the fixture's request."""
    c, call = case(name), fake.calls[i]
    assert (call[0], call[1]) == (c["request"]["method"], c["request"]["path"]), name
    if "body" in c["request"] and not str(c["request"]["body"]).startswith("<"):
        want = c["request"]["body"]
        assert {k: v for k, v in call[3].items() if not str(want.get(k, "")).startswith("<")} == {
            k: v for k, v in want.items() if not str(v).startswith("<")
        }, name
    assert call[2]["authorization"] == f"Bearer {TOKEN}"


@pytest.fixture
def clock(monkeypatch):
    slept, now = [], [0.0]

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(glyphh.client, "_sleep", sleep)
    monkeypatch.setattr(glyphh.client, "_now", lambda: now[0])
    return slept


def test_every_fixture_is_its_schema_and_the_ada_contract_is_untouched():
    assert CONTRACT["runtime"] == FIXTURES["runtime"] == 1
    for c in FIXTURES["cases"]:
        validate(c["response"]["body"], CONTRACT[c["schema"]])
        if c["response"]["status"] >= 400:
            assert c["schema"] == "error" and c["response"]["body"]["error"]["code"] in CONTRACT["codes"], c["name"]
    for code in CONTRACT["codes"]:  # every code it names is typed, or a plain RrotorError on purpose
        assert issubclass(type(glyphh.errors.runtime_error(code, "x")), AdaError)
    assert json.loads((ROOT / "contract" / "contract.json").read_text())["contract"] == glyphh.SUPPORTED_CONTRACT == 5


def test_the_address_and_the_token_default_to_the_local_rrotor(monkeypatch, tmp_path):
    monkeypatch.delenv("RROTOR_URL", raising=False)
    monkeypatch.delenv("RROTOR_TOKEN", raising=False)
    monkeypatch.setattr(glyphh.runtime.Path, "home", lambda: tmp_path)
    with pytest.raises(RrotorError) as caught:
        Runtime()
    assert caught.value.code == "E_CONFIG" and "rrotor skill" in caught.value.message
    kept = glyphh.runtime.token_path()
    assert kept == tmp_path / ".glyphh" / "rrotor" / "token"
    kept.parent.mkdir(parents=True)
    kept.write_text("from-the-file\n")
    rt = Runtime()
    assert rt.url == glyphh.DEFAULT_RUNTIME_URL == URL and rt.token == "from-the-file"
    monkeypatch.setenv("RROTOR_URL", "https://rrotor.acme.com/")
    monkeypatch.setenv("RROTOR_TOKEN", "a-runtime-key")
    rt = Runtime()
    assert rt.url == "https://rrotor.acme.com" and rt.token == "a-runtime-key"


def test_programs_are_listed_typed_a_cli_among_them():
    rt, fake = runtime(answered("the programs"))
    sales, gh = rt.programs()
    asked(fake, "the programs")
    assert (sales.name, sales.kind, sales.active, sales.is_cli) == ("daily_sales", "program", 1, False)
    assert sales.functions["start"]["approvals"] == ["write"] and sales.versions[0].commit_sha.startswith("3f1c")
    assert gh.is_cli and gh.functions == {}
    rt, _ = runtime(answered("the programs"))
    with pytest.raises(ProgramMissingError):
        rt.program("nope")


def git(folder, *args):
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


def test_a_folder_is_deployed_as_a_bundle_of_its_commit(tmp_path):
    folder = tmp_path / "daily_sales"
    folder.mkdir()
    git(folder, "init", "-q")
    git(folder, "config", "user.email", "t@example.com")
    git(folder, "config", "user.name", "t")
    (folder / "glyphh.json").write_text('{"name": "daily_sales", "functions": {"start": {}}}')
    (folder / "program.py").write_text("def start(ctx, inputs):\n    return None\n")
    git(folder, "add", ".")
    git(folder, "commit", "-qm", "first")
    sha = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    rt, fake = runtime(answered("a deploy from a bundle"))
    made = rt.deploy(folder)
    assert fake.calls[0][:2] == ("POST", "/v1/programs/deploy")
    sent = fake.calls[0][3]
    assert set(sent) == set(case("a deploy from a bundle")["request"]["body"])
    assert sent["commit"] == sha and base64.b64decode(sent["bundle"]).startswith(b"# v")  # a git bundle's header
    assert (made.program, made.version) == ("daily_sales", 1)
    bare = tmp_path / "bare"
    bare.mkdir()
    git(bare, "init", "-q")
    git(bare, "config", "user.email", "t@example.com")
    git(bare, "config", "user.name", "t")
    (bare / "README").write_text("x")
    git(bare, "add", ".")
    git(bare, "commit", "-qm", "no manifest")
    with pytest.raises(RrotorError) as caught:
        rt.deploy(bare)
    assert caught.value.code == "E_MANIFEST"
    with pytest.raises(RrotorError) as caught:
        rt.deploy(tmp_path / "nowhere")
    assert caught.value.code == "E_GIT"


def test_a_repo_is_deployed_by_its_full_commit_and_a_refused_manifest_is_typed():
    rt, fake = runtime(answered("a deploy from a repo"), answered("a manifest refused"))
    made = rt.deploy(repo="acme/daily-sales", commit="4a2d1e0f9c8b7a6d5e4f3c2b1a0d9e8f7c6b5a4d")
    asked(fake, "a deploy from a repo", 0)
    assert made.version == 2 and "token" not in fake.calls[0][3]
    with pytest.raises(ManifestError) as caught:
        rt.deploy(bundle=b"x", commit="5b3e2f1a0d9c8b7a6e5f4d3c2b1a0f9e8d7c6b5a")
    assert caught.value.status == 422 and "functions" in caught.value.message
    with pytest.raises(RrotorError):
        rt.deploy(repo="acme/daily-sales", commit="main")
    with pytest.raises(RrotorError):
        rt.deploy()


def test_a_call_waits_for_approval_then_the_persons_decision_ends_it():
    rt, fake = runtime(
        answered("a call that waits for approval"), answered("the runs waiting for approval"), answered("the run approved, done")
    )
    run = rt.call("daily_sales", "start", {"day": "2026-10-14"})
    asked(fake, "a call that waits for approval", 0)
    assert run.needs_approval and run.waiting and not run.ended and run.step == "write" and "$412.50" in run.prompt
    (waiting,) = rt.approvals()
    assert (waiting.run_id, waiting.step) == (run.run_id, "write")
    done = rt.approve(run.run_id)
    asked(fake, "the run approved, done")
    assert done.done and done.ended and done.data["written"] is True and done.exit_code is None


def test_a_runs_status_log_and_cancel():
    rt, fake = runtime(answered("a run's status"), answered("a run's log"), answered("a run cancelled"))
    info = rt.run("6f0e3c1a-2b4d-4e8f-9a1b-3c5d7e9f1a2b")
    assert (info.caller, info.status, info.ended, info.result["data"]["written"]) == ("claude", "done", True, True)
    assert rt.log("6f0e3c1a-2b4d-4e8f-9a1b-3c5d7e9f1a2b")[-1]["message"] == "written"
    assert rt.cancel("0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e").status == "cancelled"
    asked(fake, "a run cancelled")


def test_secrets_are_names_only_never_a_value_back():
    rt, fake = runtime(answered("a program's secrets"), answered("a secret set"), answered("a secret deleted"))
    (gh,) = rt.secrets("github")
    assert (gh.name, gh.declared, gh.set) == ("GH_TOKEN", True, False)
    kept = rt.set_secret("github", "GH_TOKEN", "ghp_shh")
    assert fake.calls[1][3] == {"value": "ghp_shh"}
    asked(fake, "a secret set", 1)
    assert kept.set and "ghp_shh" not in repr(kept)
    assert not rt.delete_secret("github", "GH_TOKEN").set
    asked(fake, "a secret deleted")
    with pytest.raises(RrotorError):
        rt.set_secret("github", "GH_TOKEN", 42)  # type: ignore[arg-type]


def test_schedules_are_listed_paused_and_resumed():
    rt, fake = runtime(answered("the schedules"), answered("a schedule paused"), answered("a schedule resumed"))
    (each,) = rt.schedules()
    assert (each.id, each.cron, each.paused, each.last["status"]) == ("daily_sales/each_morning", "15 6 * * *", False, "done")
    paused = rt.pause_schedule("daily_sales", "each_morning")
    asked(fake, "a schedule paused")
    assert paused.paused and paused.next_at is None
    assert not rt.resume_schedule("daily_sales", "each_morning").paused
    asked(fake, "a schedule resumed")


def test_clis_are_listed_and_a_command_runs_or_waits_for_approval():
    rt, fake = runtime(answered("the CLIs"), answered("a CLI command, done"), answered("a CLI command that waits for approval"))
    (gh,) = rt.clis()
    assert (gh.command, gh.install["source"], gh.needs_approval, gh.home) == ("gh", "url", True, True)
    done = rt.run_cli("github", ["pr", "list", "--limit", 2])
    asked(fake, "a CLI command, done", 1)
    assert done.done and done.exit_code == 0 and "Fix the ledger" in done.stdout and done.stderr == "" and done.files == {}
    waiting = rt.run_cli("github", ["pr", "merge", "41"], stdin="", files={"notes.txt": "hi"})
    assert waiting.needs_approval and waiting.step == "cli" and fake.calls[-1][3]["files"] == {"notes.txt": "hi"}


def test_the_licence_is_read_and_a_key_handed_in_as_the_body():
    rt, fake = runtime(answered("the licence, Community"), answered("a licence key handed in"))
    held = rt.licence()
    assert (held.tier, held.community, held.state, held.max_nodes) == ("free", True, "none", 1)
    got = rt.set_licence("  payload.signature\n")
    assert fake.calls[1][:2] == ("PUT", "/v1/licence") and fake.calls[1][3] == "payload.signature"
    assert got["kept"] and got["licence"].tier == "pro" and got["licence"].cluster_sync_enabled


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("a wrong token", RrotorAuthError),
        ("a program that is not there", ProgramMissingError),
        ("arguments a CLI does not allow", CliDeniedError),
        ("a run that is not waiting", RunStateError),
        ("a schedule that is not there", ScheduleMissingError),
        ("a licence on a self-hosted rrotor", LocalOnlyError),
        ("a secret set on a follower", NotHeadError),
    ],
)
def test_a_refusal_is_its_typed_error(name, error):
    rt, fake = runtime(answered(name))
    c = case(name)
    method, path = c["request"]["method"], c["request"]["path"]
    with pytest.raises(error) as caught:
        rt._call(method, path, c["request"].get("body") if method != "GET" else None)
    assert isinstance(caught.value, RrotorError) and isinstance(caught.value, AdaError)
    assert caught.value.code == c["response"]["body"]["error"]["code"] and caught.value.status == c["response"]["status"]
    if error is NotHeadError:
        assert caught.value.head == "rrotor-0"


def test_rrotor_unreachable_a_read_is_sent_again_a_write_never(clock):
    rt, fake = runtime(OSError("refused"), answered("the programs"))
    assert len(rt.programs()) == 2 and len(fake.calls) == 2 and len(clock) == 1
    rt, fake = runtime(OSError("refused"))
    with pytest.raises(RrotorError) as caught:
        rt.call("daily_sales")
    assert caught.value.code == "E_UNREACHABLE" and "127.0.0.1:7777" in caught.value.message and len(fake.calls) == 1
    rt, fake = runtime((500, "not json"))
    with pytest.raises(RrotorError) as caught:
        rt.call("daily_sales")
    assert caught.value.message == "rrotor answered 500"


def test_a_clusters_no_head_is_waited_out_and_its_seq_sent_back(clock):
    no_head = (503, {"error": {"code": "E_NO_HEAD", "message": "The cluster has no head."}}, {"Retry-After": "2"})
    rt, fake = runtime(no_head, (*answered("a call that waits for approval"), {"Rrotor-Cluster-Seq": "77"}), answered("the programs"))
    assert rt.call("daily_sales", "start", {"day": "2026-10-14"}).needs_approval and clock == [2.0]
    rt.programs()
    assert rt.cluster_seq == 77 and fake.calls[-1][2]["rrotor-min-seq"] == "77"
    rt, _ = runtime(*[no_head] * 3, retry_deadline=3)
    with pytest.raises(NoHeadError):
        rt.programs()


def test_ada_cloud_is_untouched_beside_it():
    ada = glyphh.Ada("https://ada.test", "glyphh_ak_test", transport=Fake((200, {"models": []})))
    assert ada.models() == [] and ada.url == "https://ada.test"
