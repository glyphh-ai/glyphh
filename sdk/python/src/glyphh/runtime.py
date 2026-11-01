"""A local rrotor: the runtime you install (a Docker image, bound to 127.0.0.1:7777) and drive from Claude or from
code. It hosts your programs (a glyphh.json manifest and program.py, run in a sandbox, with a local secrets vault,
local cron schedules, a SQLite database and approvals) and your CLIs (a CLI is a kind of program, `"kind": "cli"`,
run one command at a time in the same sandbox). Nothing here is Ada Cloud: programs are not Ada models, and the
Glyphh server only grants the runtime its licence.

    rt = Runtime()                                   # http://127.0.0.1:7777, the local token the installer kept
    rt.deploy("./daily_sales")                       # the folder's HEAD commit, as a git bundle
    run = rt.call("daily_sales", "start", {"day": "2026-10-30"})
    if run.needs_approval:                           # ask the person; only then
        run = rt.approve(run.run_id)                 # program_continue {"approved": true}
    print(run.status, run.data)

The address is RROTOR_URL, else http://127.0.0.1:7777; the token is RROTOR_TOKEN, else ~/.glyphh/rrotor/token
(the plugin's installer writes it, 0600). A self-hosted rrotor takes `url="https://rrotor.example.com"` and a
runtime key as the token."""

from __future__ import annotations

import base64
import json
import os
import random
import re
import subprocess  # noqa: S404  # git, to bundle a program's folder
import tempfile
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from . import client as _client
from .client import CLUSTER_SEQ, FINAL, MIN_SEQ, RETRY_DEADLINE, WAITING, Transport, _parsed, _retryable, _urllib
from .errors import AdaError, ProgramMissingError, RrotorError, runtime_error

#: Where a local rrotor answers: the host's loopback only, the port the installer publishes.
DEFAULT_RUNTIME_URL = "http://127.0.0.1:7777"
SHA = re.compile(r"^[0-9a-f]{40}$")


def token_path(home: Optional[Path] = None) -> Path:
    """Where the installer keeps the local token: ~/.glyphh/rrotor/token (0600)."""
    return (home or Path.home()) / ".glyphh" / "rrotor" / "token"


def read_token(path: Optional[Path] = None) -> Optional[str]:
    """The kept local token; None when there is none."""
    try:
        text = (path or token_path()).read_text("utf-8").strip()
    except OSError:
        return None
    return text or None


def _str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


@dataclass(frozen=True)
class Run:
    """What a call, a continue, a cancel or a CLI command answered: the run's `status` (done, needs_input,
    needs_approval, failed, expired, cancelled), its `data` (the function's answer when done; for a CLI command
    {exit_code, stdout, stderr, files, ...}), and for a waiting run the `step` and `prompt` to show the person."""

    run_id: str
    program: str
    version: int
    function: str
    status: str
    data: Any
    step: Optional[str]
    prompt: Optional[str]
    seconds: float
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def done(self) -> bool:
        return self.status == "done"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @property
    def waiting(self) -> bool:
        """It asks: `needs_input` or `needs_approval`. Answer with `Runtime.resume` (or `approve`), within 15 minutes."""
        return self.status in WAITING

    @property
    def needs_approval(self) -> bool:
        return self.status == "needs_approval"

    @property
    def needs_input(self) -> bool:
        return self.status == "needs_input"

    @property
    def ended(self) -> bool:
        return self.status in FINAL

    def _cli(self, key: str) -> Any:
        return self.data.get(key) if isinstance(self.data, dict) else None

    @property
    def exit_code(self) -> Optional[int]:
        """A CLI command's exit code (a nonzero exit is still `done`); None for a program's run."""
        code = self._cli("exit_code")
        return None if code is None else int(code)

    @property
    def stdout(self) -> Optional[str]:
        """A CLI command's stdout, its first 64 KB (all of it is in the run's log)."""
        return _str(self._cli("stdout"))

    @property
    def stderr(self) -> Optional[str]:
        return _str(self._cli("stderr"))

    @property
    def files(self) -> Optional[Dict[str, Any]]:
        """The files a CLI command made or changed in its working folder."""
        found = self._cli("files")
        return None if found is None else dict(found)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Run":
        return cls(
            run_id=str(body["run_id"]),
            program=str(body.get("program") or ""),
            version=int(body.get("version") or 0),
            function=str(body.get("function") or ""),
            status=str(body["status"]),
            data=body.get("data"),
            step=body.get("step"),
            prompt=body.get("prompt"),
            seconds=float(body.get("seconds") or 0),
            body=dict(body),
        )


@dataclass(frozen=True)
class RunInfo:
    """`GET /v1/runs/{id}`: a run's status, who called it (`caller`: claude, schedule) and from where (`origin`), its
    times, the seconds it ran (not waited) and its last Result (`result`: {data, step, prompt, ...})."""

    run_id: str
    program: str
    version: int
    function: str
    caller: Optional[str]
    origin: Optional[str]
    status: str
    created_at: Any
    updated_at: Any
    ended_at: Any
    seconds: float
    result: Optional[Dict[str, Any]]
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def waiting(self) -> bool:
        return self.status in WAITING

    @property
    def ended(self) -> bool:
        return self.status in FINAL

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "RunInfo":
        return cls(
            run_id=str(body["run_id"]),
            program=str(body.get("program") or ""),
            version=int(body.get("version") or 0),
            function=str(body.get("function") or ""),
            caller=_str(body.get("caller")),
            origin=_str(body.get("origin")),
            status=str(body["status"]),
            created_at=body.get("created_at"),
            updated_at=body.get("updated_at"),
            ended_at=body.get("ended_at"),
            seconds=float(body.get("seconds") or 0),
            result=body.get("result"),
            body=dict(body),
        )


@dataclass(frozen=True)
class ProgramVersion:
    """One deployed version of a program: its number, the commit it is, and when it was deployed. A deploy answers
    the version it made (active at once)."""

    program: str
    version: int
    commit_sha: str
    deployed_at: Any
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "ProgramVersion":
        return cls(
            program=str(body.get("program") or ""),
            version=int(body.get("version") or 0),
            commit_sha=str(body.get("commit_sha") or ""),
            deployed_at=body.get("deployed_at"),
            body=dict(body),
        )


@dataclass(frozen=True)
class Program:
    """A program (or a CLI, `kind` "cli") deployed here: its `active` version (None: none active), its `functions`
    by name ({description, inputs, approvals, writes}; a CLI has none) and every version deployed."""

    name: str
    kind: str
    description: str
    active: Optional[int]
    functions: Dict[str, Dict[str, Any]]
    versions: List[ProgramVersion]
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_cli(self) -> bool:
        return self.kind == "cli"

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Program":
        active = body.get("active")
        return cls(
            name=str(body["name"]),
            kind=str(body.get("kind") or "program"),
            description=str(body.get("description") or ""),
            active=None if active is None else int(active),
            functions={str(k): dict(v) for k, v in (body.get("functions") or {}).items()},
            versions=[ProgramVersion.of(v) for v in body.get("versions") or []],
            body=dict(body),
        )


@dataclass(frozen=True)
class Approval:
    """A run waiting for the person's approval: its program, function, `step` and `prompt` (what to show them), and
    when it asked. Approve or decline only as the person decides (`Runtime.approve`)."""

    run_id: str
    program: str
    function: str
    origin: Optional[str]
    step: Optional[str]
    prompt: Optional[str]
    asked_at: Any
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Approval":
        return cls(
            run_id=str(body["run_id"]),
            program=str(body.get("program") or ""),
            function=str(body.get("function") or ""),
            origin=_str(body.get("origin")),
            step=body.get("step"),
            prompt=body.get("prompt"),
            asked_at=body.get("asked_at"),
            body=dict(body),
        )


@dataclass(frozen=True)
class Secret:
    """A program's secret by name: whether its active version declares it, and whether it is set here. Never its
    value: rrotor keeps it encrypted and hands it only to the program's run."""

    name: str
    declared: bool
    set: bool

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Secret":
        return cls(name=str(body["name"]), declared=bool(body.get("declared")), set=bool(body.get("set")))


@dataclass(frozen=True)
class Schedule:
    """A function the runtime calls by itself, on a cron schedule in `tz`: its `id` (`<program>/<name>`), whether it
    is `paused`, when it fires next (`next_at`, None while paused), its `last` run ({run_id, at, status, code}) and
    its last skip (`skipped`: the run before had not ended)."""

    id: str
    program: str
    name: str
    version: int
    function: str
    cron: str
    tz: str
    input: Dict[str, Any]
    paused: bool
    next_at: Optional[str]
    last: Optional[Dict[str, Any]]
    skipped: Optional[Dict[str, Any]]
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Schedule":
        return cls(
            id=str(body["id"]),
            program=str(body.get("program") or ""),
            name=str(body.get("name") or ""),
            version=int(body.get("version") or 0),
            function=str(body.get("function") or ""),
            cron=str(body.get("cron") or ""),
            tz=str(body.get("tz") or "UTC"),
            input=dict(body.get("input") or {}),
            paused=bool(body.get("paused")),
            next_at=body.get("next_at"),
            last=body.get("last"),
            skipped=body.get("skipped"),
            body=dict(body),
        )


@dataclass(frozen=True)
class Cli:
    """A CLI installed here (`"kind": "cli"`): what it runs (`command`), what it was installed from (`install`:
    {source, pinned}), the argument patterns it allows (none: any) and those that wait for approval, whether it has
    a private HOME kept across calls, and the hosts it may reach."""

    name: str
    description: str
    version: int
    command: str
    install: Dict[str, Any]
    allow: List[str]
    approvals: List[str]
    needs_approval: bool
    home: bool
    hosts: List[str]
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Cli":
        return cls(
            name=str(body["name"]),
            description=str(body.get("description") or ""),
            version=int(body.get("version") or 0),
            command=str(body.get("command") or ""),
            install=dict(body.get("install") or {}),
            allow=list(body.get("allow") or []),
            approvals=list(body.get("approvals") or []),
            needs_approval=bool(body.get("needs_approval")),
            home=bool(body.get("home")),
            hosts=list(body.get("hosts") or []),
            body=dict(body),
        )


@dataclass(frozen=True)
class Licence:
    """The licence key the runtime holds and the limits that apply now. No key at all is Community (one node, no
    sync); nothing a licence does refuses a run. `state`: live, grace, expired, bad or none."""

    tier: str
    community: bool
    license_id: Optional[str]
    customer_id: Optional[str]
    source: Optional[str]
    issued_at: Optional[str]
    expires_at: Optional[str]
    state: str
    days_left: Optional[int]
    max_nodes: Optional[int]
    cluster_sync_enabled: bool
    ha: bool
    body: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Licence":
        days, nodes = body.get("days_left"), body.get("max_nodes")
        return cls(
            tier=str(body.get("tier") or ""),
            community=bool(body.get("community")),
            license_id=body.get("license_id"),
            customer_id=body.get("customer_id"),
            source=body.get("source"),
            issued_at=body.get("issued_at"),
            expires_at=body.get("expires_at"),
            state=str(body.get("state") or ""),
            days_left=None if days is None else int(days),
            max_nodes=None if nodes is None else int(nodes),
            cluster_sync_enabled=bool(body.get("cluster_sync_enabled")),
            ha=bool(body.get("ha")),
            body=dict(body),
        )


def _q(part: Any) -> str:
    return urllib.parse.quote(str(part), safe="")


def _git(folder: Path, *args: str) -> str:
    try:
        done = subprocess.run(  # noqa: S603  # git, with arguments, no shell
            ["git", "-C", str(folder), *args], capture_output=True, text=True, check=False
        )
    except OSError as e:
        raise RrotorError("E_GIT", f"git could not run: {e}") from e
    if done.returncode != 0:
        first = (done.stderr or done.stdout or "git failed").strip().splitlines()
        raise RrotorError("E_GIT", first[0] if first else "git failed")
    return done.stdout


def bundle_of(folder: Union[str, "os.PathLike[str]"], commit: Optional[str] = None) -> Dict[str, str]:
    """A program's folder at a commit, as rrotor deploys it: `{bundle, commit}`, a git bundle in base64 and the
    commit's full SHA. The folder must be a git repo with the commit made (glyphh.json at its root); nothing else
    of the machine goes to the runtime."""
    path = Path(folder).expanduser().resolve()
    wanted = commit or "HEAD"
    sha = _git(path, "rev-parse", "--verify", f"{wanted}^{{commit}}").strip()
    if not SHA.match(sha):
        raise RrotorError("E_COMMIT", f"{wanted} is not a commit in {path}.")
    try:
        _git(path, "cat-file", "-e", f"{sha}:glyphh.json")
    except RrotorError:
        raise RrotorError("E_MANIFEST", f"The commit {sha[:12]} has no glyphh.json at the folder's root.") from None
    on_head = subprocess.run(  # noqa: S603
        ["git", "-C", str(path), "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True, check=False
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "program.bundle"
        _git(path, "bundle", "create", str(out), "HEAD" if on_head.returncode == 0 else "--all")
        raw = out.read_bytes()
    return {"bundle": base64.b64encode(raw).decode("ascii"), "commit": sha}


class Runtime:
    """A rrotor: your local one by default (http://127.0.0.1:7777 and its local token), or a self-hosted one by its
    URL and a runtime key. Reads are sent again while it is unreachable for a moment; a write never is, but a
    cluster's E_NO_HEAD and a 429 are waited out (the write was not made). A cluster's `Rrotor-Cluster-Seq` is sent
    back as `Rrotor-Min-Seq`, so a read sees this client's writes on any node."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        *,
        transport: Optional[Transport] = None,
        retry_deadline: float = RETRY_DEADLINE,
        read_your_writes: bool = True,
    ) -> None:
        self.url = (url or os.environ.get("RROTOR_URL") or DEFAULT_RUNTIME_URL).rstrip("/")
        self.token = token or os.environ.get("RROTOR_TOKEN") or read_token() or ""
        if not self.token:
            raise RrotorError(
                "E_CONFIG",
                "A token is needed: install a local rrotor with the glyphh plugin's rrotor skill (it keeps the local "
                "token in ~/.glyphh/rrotor/token), or set RROTOR_TOKEN (a self-hosted rrotor's runtime key).",
            )
        self._send = transport or _urllib
        self.retry_deadline, self.read_your_writes = retry_deadline, read_your_writes
        self._seq, self._lock = 0, threading.Lock()

    @property
    def cluster_seq(self) -> int:
        """A cluster's highest `Rrotor-Cluster-Seq` answered (0: none, or a standalone rrotor)."""
        return self._seq

    # the wire

    def _call(self, method: str, path: str, body: Any = None, *, raw: Optional[bytes] = None) -> Any:
        safe = method == "GET"
        content = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        deadline, attempt = _client._now() + self.retry_deadline, 0
        while True:
            try:
                return self._once(method, path, content, json_body=raw is None)
            except AdaError as err:
                if not _retryable(err, safe):
                    raise
                wait = err.retry_after
                if wait is None:
                    wait = min(2.0, 0.25 * 2**attempt) * (0.5 + random.random() / 2)  # noqa: S311
                if _client._now() + wait > deadline:
                    raise
                _client._sleep(wait)
                attempt += 1

    def _once(self, method: str, path: str, content: Optional[bytes], json_body: bool = True) -> Any:
        headers = {"authorization": f"Bearer {self.token}", "accept": "application/json"}
        if content is not None:
            headers["content-type"] = "application/json" if json_body else "text/plain"
        if self.read_your_writes and self._seq:
            headers[MIN_SEQ] = str(self._seq)
        try:
            answer = self._send(method, f"{self.url}{path}", headers, content)
        except OSError as e:
            raise RrotorError(
                "E_UNREACHABLE",
                f"rrotor is not answering at {self.url}: {e}. Is it running? (`docker ps --filter name=glyphh-rrotor`; "
                "the glyphh plugin's rrotor skill installs and starts it.)",
            ) from e
        got = {str(k).lower(): str(v) for k, v in (answer[2] if len(answer) > 2 else {}).items()}  # type: ignore[misc]
        try:
            seq = int(got.get(CLUSTER_SEQ) or 0)
        except ValueError:
            seq = 0
        with self._lock:
            self._seq = max(self._seq, seq)
        return _parsed(answer[0], answer[1], got, runtime_error)

    # the runtime

    def health(self) -> Dict[str, Any]:
        """Its version, mode, the sandbox's layers, the licence, the cluster, runs waiting for approval and how many
        programs it holds."""
        return dict(self._call("GET", "/v1/health"))

    def licence(self) -> Licence:
        """The licence key held and the limits that apply (Community with none)."""
        return Licence.of(self._call("GET", "/v1/licence")["licence"])

    def set_licence(self, key: str) -> Dict[str, Any]:
        """Hand a licence key to a local rrotor: {licence, kept} (`kept` False: a newer key is held). A self-hosted
        rrotor reads its key from its environment: LocalOnlyError. A bad key: LicenceError."""
        got = self._call("PUT", "/v1/licence", raw=key.strip().encode())
        return {"licence": Licence.of(got["licence"]), "kept": bool(got.get("kept"))}

    # programs

    def programs(self) -> List[Program]:
        """Every program and CLI deployed here: its versions, the active one, its functions."""
        return [Program.of(p) for p in self._call("GET", "/v1/programs")["programs"]]

    def program(self, name: str) -> Program:
        found = next((p for p in self.programs() if p.name == name), None)
        if found is None:
            raise ProgramMissingError("E_PROGRAM_MISSING", f"No program {name} is deployed here.", 404, {"program": name})
        return found

    def deploy(
        self,
        path: Optional[Union[str, "os.PathLike[str]"]] = None,
        *,
        commit: Optional[str] = None,
        repo: Optional[str] = None,
        token: Optional[str] = None,
        bundle: Optional[bytes] = None,
    ) -> ProgramVersion:
        """A program's (or a CLI's) next version, active at once: from a folder on this machine at a commit (`path`;
        `commit` HEAD by default: commit first), from a GitHub repo (`repo` owner/name and `commit`, the full SHA;
        `token` for a private one), or from a git bundle's bytes and its `commit`. rrotor checks the commit and the
        manifest (ManifestError) and makes the venv from requirements.lock; a CLI's pinned install is fetched and
        checked."""
        if path is not None:
            body: Dict[str, Any] = bundle_of(path, commit)
        elif repo is not None:
            if not commit or not SHA.match(commit):
                raise RrotorError("E_COMMIT", "A deploy from a repo names its commit: the full 40-character SHA.")
            body = {"repo": repo, "commit": commit, **({} if token is None else {"token": token})}
        elif bundle is not None and commit:
            body = {"bundle": base64.b64encode(bundle).decode("ascii"), "commit": commit}
        else:
            raise RrotorError("E_BAD_REQUEST", "Deploy a folder (path), a repo and its commit, or a bundle and its commit.")
        return ProgramVersion.of(self._call("POST", "/v1/programs/deploy", body))

    def call(
        self,
        program: str,
        function: str = "start",
        inputs: Optional[Mapping[str, Any]] = None,
        *,
        version: Optional[int] = None,
        clearance: Optional[float] = None,
    ) -> Run:
        """Open a run of a program's function, in the sandbox: its first Result. The inputs are checked against the
        function's schema (InputsError). A failed run is a Result, never an exception."""
        body: Dict[str, Any] = {"program": program, "function": function, "inputs": dict(inputs or {})}
        if version is not None:
            body["version"] = version
        if clearance is not None:
            body["clearance"] = clearance
        return Run.of(self._call("POST", "/v1/runs", body))

    def resume(self, run_id: str, answer: Any) -> Run:
        """Answer a waiting run (MCP's program_continue): for needs_approval {"approved": True | False}, only as the
        person decided; for needs_input the value or choice. The next Result."""
        return Run.of(self._call("POST", f"/v1/runs/{_q(run_id)}/continue", {"answer": answer}))

    def approve(self, run_id: str, approved: bool = True) -> Run:
        """`resume(run_id, {"approved": approved})`: the person's decision on a needs_approval run."""
        return self.resume(run_id, {"approved": bool(approved)})

    def cancel(self, run_id: str) -> Run:
        """Stop a run; its `end` runs; `cancelled`."""
        return Run.of(self._call("POST", f"/v1/runs/{_q(run_id)}/cancel", {}))

    def run(self, run_id: str) -> RunInfo:
        """A run's status, times and last Result."""
        return RunInfo.of(self._call("GET", f"/v1/runs/{_q(run_id)}"))

    def log(self, run_id: str) -> List[Any]:
        """A run's log lines (secret values masked)."""
        return list(self._call("GET", f"/v1/runs/{_q(run_id)}/log")["lines"])

    def approvals(self) -> List[Approval]:
        """The runs waiting for the person's approval (a cluster's, every node's)."""
        return [Approval.of(a) for a in self._call("GET", "/v1/approvals")["approvals"]]

    # secrets: names only, never a value back

    def secrets(self, program: str) -> List[Secret]:
        """A program's secrets by name: declared by its active version, set here. Never a value."""
        return [Secret.of(s) for s in self._call("GET", f"/v1/programs/{_q(program)}/secrets")["secrets"]]

    def set_secret(self, program: str, name: str, value: str) -> Secret:
        """Keep a secret's value for a program, encrypted on the runtime; answers its name, never the value."""
        if not isinstance(value, str):
            raise RrotorError("E_BAD_REQUEST", "A secret's value is a string.")
        got = self._call("PUT", f"/v1/programs/{_q(program)}/secrets/{_q(name)}", {"value": value})
        return Secret(name=str(got.get("name") or name), declared=True, set=bool(got.get("set", True)))

    def delete_secret(self, program: str, name: str) -> Secret:
        got = self._call("DELETE", f"/v1/programs/{_q(program)}/secrets/{_q(name)}")
        return Secret(name=str(got.get("name") or name), declared=True, set=bool(got.get("set", False)))

    # schedules

    def schedules(self) -> List[Schedule]:
        """Every program's schedules, which the runtime fires itself."""
        return [Schedule.of(s) for s in self._call("GET", "/v1/schedules")["schedules"]]

    def pause_schedule(self, program: str, name: str) -> Schedule:
        """Pause a schedule, kept across restarts and new versions."""
        return Schedule.of(self._call("POST", f"/v1/schedules/{_q(program)}/{_q(name)}/pause", {}))

    def resume_schedule(self, program: str, name: str) -> Schedule:
        return Schedule.of(self._call("POST", f"/v1/schedules/{_q(program)}/{_q(name)}/resume", {}))

    # CLIs

    def clis(self) -> List[Cli]:
        """The CLIs installed here."""
        return [Cli.of(c) for c in self._call("GET", "/v1/clis")["clis"]]

    def run_cli(
        self,
        cli: str,
        args: Sequence[str] = (),
        *,
        stdin: Optional[str] = None,
        files: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        """One command of a CLI in the sandbox (MCP's cli_run): `done` with exit_code, stdout and stderr (a nonzero
        exit is still done), or `needs_approval` when its arguments match an approval pattern (then `approve`).
        Arguments `allow` does not take: CliDeniedError. `files` (relative path: text, or {"base64": ...}) are
        written to the command's working folder."""
        body: Dict[str, Any] = {"args": [str(a) for a in args]}
        if stdin is not None:
            body["stdin"] = stdin
        if files is not None:
            body["files"] = dict(files)
        return Run.of(self._call("POST", f"/v1/clis/{_q(cli)}/run", body))
