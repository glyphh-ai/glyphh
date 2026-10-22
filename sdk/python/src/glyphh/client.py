"""The client: Ada Cloud at https://ada.glyphh.ai and an API key; every call is one request to Ada's API (a job-backed
call, one request and then its job's progress)."""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .errors import AdaError, AdaTimeoutError, JobFailedError, ReadOnlyError, error

#: Where Ada answers. GLYPHH_ADA_URL (or 3.0's GLYPHH_RUNTIME_URL) moves it, e.g. to a local server under test.
DEFAULT_URL = "https://ada.glyphh.ai"
DEFAULT_TIMEOUT = 90.0
#: How long, in seconds, a call keeps retrying what is safe to send again before it raises.
RETRY_DEADLINE = 30.0
#: How long, in seconds, waiting for a job lasts before it raises (the job goes on; wait for it again by its id).
JOB_TIMEOUT = 3600.0
#: The longest pause, in seconds, between two looks at a job.
POLL = 2.0
#: Cases one record_many request carries; record_many sends more in chunks of this many.
RECORD_MANY_MAX = 1000
WAITING = ("needs_input", "needs_approval")
FINAL = ("done", "failed", "expired", "cancelled")
#: An Ada model's functions that only read: safe to send again when Ada could not be reached.
READS = ("query", "facts", "probabilities", "decide")
CLUSTER_SEQ, MIN_SEQ = "rrotor-cluster-seq", "rrotor-min-seq"
#: An import's format by its file's extension.
FORMATS = {
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".csv": "csv",
    ".sqlite": "ada_sqlite",
    ".db": "ada_sqlite",
    ".zip": "jsonl",  # a model's own export
}

#: Sends one request: (method, url, headers, body) -> (status, body bytes) or (status, body bytes, headers).
#: Give your own to use another HTTP library; answer the headers for Retry-After.
Transport = Callable[
    [str, str, Mapping[str, str], Optional[bytes]],
    Union[Tuple[int, bytes], Tuple[int, bytes, Mapping[str, str]]],
]
Progress = Callable[["Job"], None]

_sleep, _now = time.sleep, time.monotonic  # the tests' seams


@dataclass(frozen=True)
class Result:
    """What a run answered (`POST /v1/runs`, SDK 3.0's call shape): its status, and its data (the function's answer
    when done; why, when failed). Ada Cloud answers every run at once, `done`."""

    run_id: str
    model: str
    version: int
    function: str
    status: str
    data: Any
    step: Optional[str]
    prompt: Optional[str]
    seconds: float

    @property
    def done(self) -> bool:
        return self.status == "done"

    @property
    def waiting(self) -> bool:
        """The run asks: `needs_input` or `needs_approval` (a self-hosted runtime's; the cloud answers `ask`)."""
        return self.status in WAITING

    @property
    def ended(self) -> bool:
        return self.status in FINAL

    @property
    def limit_exceeded(self) -> bool:
        """A self-hosted runtime's: done but indexed nothing, the store at its licence's cap. The cloud refuses with
        `LimitError` instead."""
        return self.done and isinstance(self.data, dict) and self.data.get("status") == "limit_exceeded"

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Result":
        return cls(
            run_id=str(body["run_id"]),
            model=str(body["model"]),
            version=int(body["version"]),
            function=str(body["function"]),
            status=str(body["status"]),
            data=body.get("data"),
            step=body.get("step"),
            prompt=body.get("prompt"),
            seconds=float(body.get("seconds", 0)),
        )


@dataclass(frozen=True)
class Decision:
    """`POST /v1/decide`: the outcome of least expected cost under the spec's costs, the calibrated probabilities,
    whether a person should decide instead (`ask`; the outcome is then the best guess, for them to see), and the
    precedents it stands on. `facts` when asked for (`include=["facts"]`); `outputs` when several outputs were
    decided at once, each a Decision. It reads as a 3.0 `Result` too: `done`, `status` and `data` (the answer)."""

    outcome: Optional[str]
    probabilities: Dict[str, float]
    expected_cost: Optional[float]
    ask: bool
    receipts: List[Dict[str, Any]]
    model: str
    version: int
    facts: Optional[List[Any]] = None
    outputs: Optional[Dict[str, "Decision"]] = None
    data: Dict[str, Any] = field(default_factory=dict, repr=False)

    # 3.0's Result, for code written to it
    status = "done"
    function = "decide"
    run_id = ""
    step = None
    prompt = None
    seconds = 0.0
    done = True
    waiting = False
    ended = True
    limit_exceeded = False

    @classmethod
    def of(cls, body: Mapping[str, Any], model: str = "", version: int = 0) -> "Decision":
        model, version = str(body.get("model") or model), int(body.get("version") or version)
        found = body.get("outputs")
        outputs = None if found is None else {k: cls.of(v, model, version) for k, v in found.items()}
        ask = bool(body["ask"]) if "ask" in body else any(d.ask for d in (outputs or {}).values())
        return cls(
            outcome=body.get("outcome"),
            probabilities=dict(body.get("probabilities") or {}),
            expected_cost=body.get("expected_cost"),
            ask=ask,
            receipts=list(body.get("receipts") or []),
            model=model,
            version=version,
            facts=body.get("facts"),
            outputs=outputs,
            data=dict(body),
        )


@dataclass(frozen=True)
class Job:
    """Work too long for a request (learn, calibrate, import, export, backtest, re-encode): its state (`awaiting`
    its file, `queued`, `running`, `done`, `failed`), `percent`, and its `result` or `error`. A done export carries
    `download` ({url, expires_at}); an import waiting for its file, `upload`."""

    id: str
    model: str
    kind: str
    state: str
    percent: float
    result: Any
    error: Optional[Dict[str, Any]]
    download: Optional[Dict[str, Any]] = None
    upload: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def done(self) -> bool:
        return self.state == "done"

    @property
    def failed(self) -> bool:
        return self.state == "failed"

    @property
    def ended(self) -> bool:
        return self.state in ("done", "failed")

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Job":
        return cls(
            id=str(body["id"]),
            model=str(body.get("model") or ""),
            kind=str(body["kind"]),
            state=str(body["state"]),
            percent=float(body.get("percent") or 0),
            result=body.get("result"),
            error=body.get("error"),
            download=body.get("download"),
            upload=body.get("upload"),
            data=dict(body),
        )


def _count(value: Any) -> Optional[int]:
    return None if value is None else int(value)


@dataclass(frozen=True)
class Held:
    """The precedents the org's models hold together, against the plan's (`max` None: by contract, no cap)."""

    used: int
    max: Optional[int]


@dataclass(frozen=True)
class Requests:
    """The org's requests this month (reads: decide, query, probabilities, facts; a decide of several outputs once per
    output) against the plan's month (`max` None: by contract). `overage`: past the month the reads go on, metered
    (Basic, Pro, Team), `over` of them so far; else (Free) they are refused, LimitError `requests`, until `resets_at`."""

    used: int
    max: Optional[int]
    over: int
    overage: bool


@dataclass(frozen=True)
class Usage:
    """`GET /v1/usage`: what the org uses of Ada Cloud against its plan, in the calendar `month` counted (YYYY-MM,
    UTC), which starts again on `resets_at` (YYYY-MM-DD): its live `models`, the `precedents` they hold, its
    `requests`, and the calls a second the plan allows (`requests_per_second`, None: by contract). Reads as the
    answer's dict too (`usage["plan"]`)."""

    plan: str
    month: str
    resets_at: str
    models: int
    precedents: Held
    requests: Requests
    requests_per_second: Optional[int]
    data: Dict[str, Any] = field(default_factory=dict, repr=False)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    @classmethod
    def of(cls, body: Mapping[str, Any]) -> "Usage":
        held, reads = body.get("precedents") or {}, body.get("requests") or {}
        return cls(
            plan=str(body.get("plan") or ""),
            month=str(body.get("month") or ""),
            resets_at=str(body.get("resets_at") or ""),
            models=int(body.get("models") or 0),
            precedents=Held(used=int(held.get("used") or 0), max=_count(held.get("max"))),
            requests=Requests(
                used=int(reads.get("used") or 0),
                max=_count(reads.get("max")),
                over=int(reads.get("over") or 0),
                overage=bool(reads.get("overage")),
            ),
            requests_per_second=_count(body.get("requests_per_second")),
            data=dict(body),
        )


def _urllib(
    method: str, url: str, headers: Mapping[str, str], body: Optional[bytes]
) -> Tuple[int, bytes, Dict[str, str]]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:  # noqa: S310  # Ada's own address
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers.items())


def _retry_after(value: Optional[str]) -> Optional[float]:
    """Retry-After as seconds: a number of them, or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


TRANSIENT = ("E_UNREACHABLE", "E_UNAVAILABLE", "E_TIMEOUT")


def _retryable(err: AdaError, safe: bool) -> bool:
    """Refused before anything ran (429, a self-hosted cluster's E_NO_HEAD): any call. Ada unreachable for a moment
    (E_UNREACHABLE, E_UNAVAILABLE, E_TIMEOUT, a proxy's 502, 503, 504): a call that is safe to send again, a read or
    a write carrying an Idempotency-Key (made once however often it is sent)."""
    if err.code == "E_NO_HEAD" or err.status == 429:
        return True
    return safe and (err.code in TRANSIENT or err.status in (502, 503, 504))


def _result(body: Mapping[str, Any]) -> Result:
    r = Result.of(body)
    if r.status == "failed" and isinstance(r.data, dict) and r.data.get("code") == "E_READ_ONLY":
        reason = str(r.data.get("reason") or f"{r.function} wrote, and it is marked read-only")
        raise ReadOnlyError("E_READ_ONLY", reason, 200, {"run_id": r.run_id, "function": r.function})
    return r


def _parsed(status: int, content: bytes, got: Mapping[str, str]) -> Any:
    """An answer's JSON, or its refusal raised as the typed error."""
    try:
        parsed = json.loads(content) if content else {}
    except ValueError:
        parsed = {}
    if status >= 400:
        err = parsed.get("error", {}) if isinstance(parsed, dict) else {}
        fallback = {401: "E_AUTH", 402: "E_LIMIT", 404: "E_NOT_FOUND", 429: "E_RATE"}.get(status, "E_RUNTIME")
        code = err.get("code") or fallback
        detail = {k: v for k, v in err.items() if k not in ("code", "message")}
        message = err.get("message") or f"Ada answered {status}"
        raise error(code, message, status, detail, _retry_after(got.get("retry-after")))
    return parsed


def _quote(part: Any) -> str:
    return urllib.parse.quote(str(part), safe="")


def _drop_none(**values: Any) -> Dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


class Ada:
    """Ada Cloud, for one API key.

        ada = Ada()                                    # GLYPHH_API_KEY from the environment; https://ada.glyphh.ai
        d = ada.decide("tickets", {"ticket": {...}})
        if d.ask: send_to_a_person(d)                  # d.outcome is the best guess, for them to see
        else: act(d.outcome)

    Calls safe to send again (reads, and writes, which carry an Idempotency-Key) are retried while Ada is unreachable
    for a moment, with backoff (Retry-After honoured), for up to `retry_deadline` seconds (0: never).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        *,
        transport: Optional[Transport] = None,
        retry_deadline: float = RETRY_DEADLINE,
        read_your_writes: bool = True,
    ) -> None:
        found = url or os.environ.get("GLYPHH_ADA_URL") or os.environ.get("GLYPHH_RUNTIME_URL") or DEFAULT_URL
        self.url = found.rstrip("/")
        self.key = key or os.environ.get("GLYPHH_API_KEY") or os.environ.get("GLYPHH_RUNTIME_KEY") or ""
        if not self.key:
            raise AdaError(
                "E_CONFIG",
                "An API key is needed: set GLYPHH_API_KEY (make one on the platform's API Keys page, or ask Claude "
                "through the Glyphh connector).",
            )
        self._send = transport or _urllib
        self.retry_deadline, self.read_your_writes = retry_deadline, read_your_writes
        self._seq, self._lock = 0, threading.Lock()

    @property
    def cluster_seq(self) -> int:
        """A self-hosted cluster's highest `Rrotor-Cluster-Seq` answered (0: none; always 0 against the cloud)."""
        return self._seq

    # the wire

    def _call(
        self,
        method: str,
        path: str,
        body: Optional[Mapping[str, Any]] = None,
        *,
        read: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        """One request, sent again while it may be (`_retryable`) and the deadline allows. `read`: safe to send again
        (a GET by default); a write with an `idempotency_key` is safe too."""
        safe = (method == "GET" if read is None else read) or idempotency_key is not None
        raw = None if body is None else json.dumps(body).encode()
        extra = {} if idempotency_key is None else {"idempotency-key": idempotency_key}
        deadline, attempt = _now() + self.retry_deadline, 0
        while True:
            try:
                return self._once(method, path, raw, extra)
            except AdaError as err:
                if not _retryable(err, safe):
                    raise
                wait = err.retry_after
                if wait is None:  # 0.25 s doubling to 2 s, jittered by up to half
                    wait = min(2.0, 0.25 * 2**attempt) * (0.5 + random.random() / 2)  # noqa: S311
                if _now() + wait > deadline:
                    raise
                _sleep(wait)
                attempt += 1

    def _write(self, method: str, path: str, body: Optional[Mapping[str, Any]] = None, key: Optional[str] = None) -> Any:
        """A write to the cloud: it carries an Idempotency-Key (the caller's, or a new one), so it is made once."""
        return self._call(method, path, body, idempotency_key=key or uuid.uuid4().hex)

    def _exchange(
        self, method: str, url: str, headers: Mapping[str, str], raw: Optional[bytes]
    ) -> Tuple[int, bytes, Dict[str, str]]:
        try:
            answer = self._send(method, url, headers, raw)
        except OSError as e:
            raise AdaError("E_UNREACHABLE", f"Ada could not be reached: {e}") from e
        got = {str(k).lower(): str(v) for k, v in (answer[2] if len(answer) > 2 else {}).items()}  # type: ignore[misc]
        return answer[0], answer[1], got

    def _once(self, method: str, path: str, raw: Optional[bytes], extra: Optional[Mapping[str, str]] = None) -> Any:
        headers = {"authorization": f"Bearer {self.key}", "accept": "application/json", **(extra or {})}
        if raw is not None:
            headers["content-type"] = "application/json"
        if self.read_your_writes and self._seq:
            headers[MIN_SEQ] = str(self._seq)
        status, content, got = self._exchange(method, f"{self.url}{path}", headers, raw)
        self._saw(got.get(CLUSTER_SEQ))
        return _parsed(status, content, got)

    def _saw(self, seq: Optional[str]) -> None:
        try:
            n = int(seq or 0)
        except ValueError:
            return
        with self._lock:
            self._seq = max(self._seq, n)

    # models

    def models(self) -> List[Dict[str, Any]]:
        """The org's models: each one's name, active version and how many precedents it holds."""
        return list(self._call("GET", "/v1/models")["models"])

    def model(self, name: str) -> "Model":
        return Model(self, name)

    def create_model(self, name: str, spec: Mapping[str, Any], *, idempotency_key: Optional[str] = None) -> "Model":
        """A model from its JSON spec, checked by the kernel and the cloud's bounds: version 1, empty. Its name is
        lower case letters, digits and `_ . -`, at most 63. `Model.created` is the answer."""
        made = self._write("POST", "/v1/models", {"name": name, "spec": dict(spec)}, idempotency_key)
        return Model(self, name, made)

    def delete_model(self, name: str) -> Dict[str, Any]:
        """Delete a model and every precedent it holds. Not undone."""
        return dict(self._write("DELETE", f"/v1/models/{_quote(name)}?confirm={_quote(name)}"))

    # asking

    def decide(
        self,
        model: str,
        data: Mapping[str, Any],
        *,
        output: Optional[str] = None,
        outputs: Optional[Sequence[str]] = None,
        include: Optional[Sequence[str]] = None,
        clearance: Optional[float] = None,
    ) -> Decision:
        """The headline, `POST /v1/decide`: one call, one typed answer. `outputs` decides several of the model's
        named outputs at once; `include=["facts"]` adds the nearest fact tree; `clearance` reads with less than the
        key's."""
        body = _drop_none(
            model=model,
            data=dict(data),
            output=output,
            outputs=None if outputs is None else list(outputs),
            include=None if include is None else list(include),
            clearance=clearance,
        )
        return Decision.of(self._call("POST", "/v1/decide", body, read=True))

    # jobs

    def job(self, job_id: str) -> Job:
        """A job's state and progress."""
        return Job.of(self._call("GET", f"/v1/jobs/{_quote(job_id)}"))

    def wait(
        self,
        job: Union[Job, str],
        *,
        timeout: float = JOB_TIMEOUT,
        poll: float = POLL,
        on_progress: Optional[Progress] = None,
    ) -> Job:
        """Wait for a job to end: the done job, or `JobFailedError` with the job's own error. `on_progress` gets the
        job each time it is looked at. Past `timeout` seconds, `AdaTimeoutError` (the job goes on)."""
        current = self.job(job) if isinstance(job, str) else job
        deadline, pause = _now() + timeout, 0.25
        while True:
            if on_progress is not None:
                on_progress(current)
            if current.failed:
                err = dict(current.error or {})
                raise JobFailedError(
                    str(err.pop("code", "E_JOB_FAILED")),
                    str(err.pop("message", f"The {current.kind} job failed.")),
                    0,
                    {**err, "job": current.data},
                )
            if current.done:
                return current
            if _now() + pause > deadline:
                raise AdaTimeoutError(
                    "E_TIMEOUT",
                    f"The {current.kind} job {current.id} did not end within {timeout:g} s; it goes on: wait for it "
                    "again by its id.",
                    0,
                    {"job": current.id},
                )
            _sleep(pause)
            pause = min(poll, pause * 2)
            current = self.job(current.id)

    def download(self, job: Union[Job, str]) -> bytes:
        """A done export's file, by its job or its download URL: the link is its own credential, for an hour."""
        target = job if isinstance(job, str) else (job.download or {}).get("url")
        if not target:
            raise AdaError("E_INVALID", "This job has no download link: export, and wait for it to be done.")
        status, content, got = self._exchange("GET", target, {"accept": "*/*"}, None)
        if status >= 400:
            _parsed(status, content, got)
        return content

    def usage(self) -> Usage:
        """What the org uses of Ada Cloud against its plan: its models, the precedents they hold, and its requests
        this calendar month (UTC), with when they start again and the calls a second the plan allows."""
        return Usage.of(self._call("GET", "/v1/usage"))

    # SDK 3.0's calls for a self-hosted runtime: the cloud keeps no runs and deploys no repos

    def deploy(self, repo: str, commit: str, token: Optional[str] = None) -> Dict[str, Any]:
        """A self-hosted runtime's: a commit of a model's GitHub repo as its next version. The cloud has no deploys:
        a model is its spec (`create_model`, `Model.set_spec`)."""
        return dict(self._call("POST", "/v1/models/deploy", _drop_none(repo=repo, commit=commit, token=token)))

    def run(self, run_id: str) -> Dict[str, Any]:
        """A self-hosted runtime's run. The cloud answers every run at once and keeps none (E_RUN_MISSING)."""
        return dict(self._call("GET", f"/v1/runs/{_quote(run_id)}"))

    def log(self, run_id: str) -> List[Any]:
        return list(self._call("GET", f"/v1/runs/{_quote(run_id)}/log")["lines"])

    def resume(self, run_id: str, answer: Any) -> Result:
        """A self-hosted runtime's run that waits. The cloud never waits: a decision says `ask` instead."""
        return _result(self._call("POST", f"/v1/runs/{_quote(run_id)}/continue", {"answer": answer}))

    def cancel(self, run_id: str) -> Result:
        return _result(self._call("POST", f"/v1/runs/{_quote(run_id)}/cancel", {}))


class Model:
    """One model of the org. SDK 3.0's calls (`call`, `record`, `query`, `facts`, `probabilities`, `learn`) answer a
    `Result` as they did; the rest are the cloud's own."""

    def __init__(self, ada: Ada, name: str, created: Optional[Mapping[str, Any]] = None) -> None:
        self.ada, self.name = ada, name
        self.created = None if created is None else dict(created)  # create_model's answer

    def _path(self, rest: str = "") -> str:
        return f"/v1/models/{_quote(self.name)}{rest}"

    # the model

    def info(self) -> Dict[str, Any]:
        """The model: its active version and spec, and how many precedents it holds."""
        return dict(self.ada._call("GET", self._path()))

    def delete(self) -> Dict[str, Any]:
        """Delete the model and every precedent it holds. Not undone."""
        return self.ada.delete_model(self.name)

    def spec(self) -> Dict[str, Any]:
        """The active version's spec."""
        return dict(self.info()["spec"])

    def _change(
        self, made: Mapping[str, Any], wait: bool, timeout: float, on_progress: Optional[Progress]
    ) -> Dict[str, Any]:
        out = dict(made)
        if out.get("job") is not None:
            job = Job.of(out["job"])
            out["job"] = self.ada.wait(job, timeout=timeout, on_progress=on_progress) if wait else job
        return out

    def set_spec(
        self,
        spec: Mapping[str, Any],
        *,
        note: Optional[str] = None,
        backtest: Optional[str] = None,
        wait: bool = True,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """A new version from a whole spec: {version, active, job}. Active at once when it reads the stored cases as
        they are; else `job` re-encodes them while the old version serves (waited for unless `wait=False`). A role
        read another way is refused (`SpecReadingError`). `backtest`: the backtest job that chose it, kept."""
        body = _drop_none(spec=dict(spec), note=note, backtest=backtest)
        made = self.ada._write("PUT", self._path("/spec"), body, idempotency_key)
        return self._change(made, wait, timeout, on_progress)

    def settings(
        self,
        changes: Optional[Mapping[str, Any]] = None,
        *,
        note: Optional[str] = None,
        backtest: Optional[str] = None,
        wait: bool = True,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """No changes: every lever as it stands, {version, settings}. With changes ({lever: value}): a new version
        with them, {version, active, job}, as `set_spec`."""
        if changes is None:
            return dict(self.ada._call("GET", self._path("/settings")))
        body = _drop_none(changes=dict(changes), note=note, backtest=backtest)
        made = self.ada._write("PATCH", self._path("/settings"), body, idempotency_key)
        return self._change(made, wait, timeout, on_progress)

    def versions(self) -> List[Dict[str, Any]]:
        """Every version: who made it and why, which is active."""
        return list(self.ada._call("GET", self._path("/versions"))["versions"])

    def activate(
        self, version: int, *, wait: bool = True, timeout: float = JOB_TIMEOUT, on_progress: Optional[Progress] = None
    ) -> Dict[str, Any]:
        """Make another version active (a rollback): at once, or by a job bringing its store up to date first."""
        made = self.ada._write("POST", self._path(f"/versions/{int(version)}/activate"), {})
        return self._change(made, wait, timeout, on_progress)

    # cases

    def record_many(
        self, cases: Iterable[Mapping[str, Any]], *, idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cases ({data, outcome?, outcomes?, ts?}), a thousand a request, each request one transaction:
        {ids, added, replaced, precedents}. Each request carries an Idempotency-Key (`idempotency_key`, with the
        chunk's number after the first), so a request sent again is made once."""
        total: Dict[str, Any] = {"ids": [], "added": 0, "replaced": 0, "precedents": 0}
        batch: List[Dict[str, Any]] = []
        sent = 0

        def send() -> None:
            nonlocal sent
            key = None if idempotency_key is None else (idempotency_key if sent == 0 else f"{idempotency_key}.{sent}")
            got = self.ada._write("POST", self._path("/record_many"), {"cases": batch}, key)
            total["ids"] += list(got.get("ids", []))
            total["added"] += int(got.get("added", 0))
            total["replaced"] += int(got.get("replaced", 0))
            total["precedents"] = got.get("precedents", total["precedents"])
            sent += 1

        for case in cases:
            batch.append(dict(case))
            if len(batch) == RECORD_MANY_MAX:
                send()
                batch = []
        if batch or sent == 0:
            send()
        return total

    def grade(self, precedent_id: str, value: Optional[str], *, output: Optional[str] = None) -> Dict[str, Any]:
        """One output's outcome on a case already recorded (None takes it away)."""
        body = {"id": precedent_id, "value": value, **_drop_none(output=output)}
        return dict(self.ada._write("POST", self._path("/grade"), body))

    def forget(self, precedent_id: str) -> Dict[str, Any]:
        """Forget one case; what was learned from it stays until the next learn."""
        return dict(self.ada._write("DELETE", self._path(f"/precedents/{_quote(precedent_id)}")))

    # asking

    def decide(
        self,
        data: Mapping[str, Any],
        *,
        output: Optional[str] = None,
        outputs: Optional[Sequence[str]] = None,
        include: Optional[Sequence[str]] = None,
        clearance: Optional[float] = None,
    ) -> Decision:
        """`Ada.decide` for this model."""
        return self.ada.decide(self.name, data, output=output, outputs=outputs, include=include, clearance=clearance)

    # learning and tuning, as jobs

    def learn_job(
        self, *, wait: bool = True, timeout: float = JOB_TIMEOUT, on_progress: Optional[Progress] = None
    ) -> Job:
        """`learn` as the job it is, with its progress: the weights from the graded precedents, then calibration."""
        return self._job("/learn", None, wait, timeout, on_progress)

    def calibrate(
        self, *, wait: bool = True, timeout: float = JOB_TIMEOUT, on_progress: Optional[Progress] = None
    ) -> Job:
        """Fit the temperature alone, so the probabilities mean what they say (or decide best, by the costs)."""
        return self._job("/calibrate", None, wait, timeout, on_progress)

    def backtest(
        self,
        candidates: Sequence[Mapping[str, Any]] = (),
        *,
        holdout: Optional[Mapping[str, Any]] = None,
        output: Optional[str] = None,
        clearance: Optional[float] = None,
        wait: bool = True,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
    ) -> Job:
        """Score the active version and up to ten candidates ({settings}, {spec_version} or {spec}, each with an
        optional name) on the model's own held-out precedents (`holdout` {newest: n}, 200 by default, or {fraction,
        seed}), each learned on the rest. The live model is never touched. The job's `result` has, per candidate,
        accuracy, log-loss, cost, ask rate, coverage, calibration error and the mistakes."""
        body = _drop_none(
            candidates=[dict(c) for c in candidates],
            holdout=None if holdout is None else dict(holdout),
            output=output,
            clearance=clearance,
        )
        return self._job("/backtest", body, wait, timeout, on_progress)

    def _job(
        self, rest: str, body: Optional[Mapping[str, Any]], wait: bool, timeout: float, on_progress: Optional[Progress]
    ) -> Job:
        job = Job.of(self.ada._write("POST", self._path(rest), body or {}))
        return self.ada.wait(job, timeout=timeout, on_progress=on_progress) if wait else job

    # in and out

    def import_file(
        self,
        source: Union[str, "os.PathLike[str]", bytes],
        *,
        format: Optional[str] = None,  # noqa: A002  # the API's own name
        mapping: Optional[Mapping[str, Optional[str]]] = None,
        partial: bool = False,
        learn: bool = True,
        wait: bool = True,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
    ) -> Job:
        """A file of cases into the model, as a job: JSON Lines ({data, outcome?, outcomes?, ts?, id?} a line), CSV
        (a header names a role's path, `outcome` or `outcome.<output>`; `mapping` maps other headers, None skips
        one), `ada_sqlite` (a kernel store), or a model's own export (a zip, as jsonl). The format is read from the
        file's extension when not given. The file goes to a one-hour signed upload link, then the import runs; rows
        the spec refuses are named in the result and the rest go in. `partial`: past the plan's cap, record up to
        it. `learn`: learn and calibrate once at the end."""
        if isinstance(source, (bytes, bytearray)):
            content = bytes(source)
            if format is None:
                raise AdaError("E_INVALID", "Say the format of a file given as bytes: jsonl, csv or ada_sqlite.")
        else:
            path = Path(source)
            format = format or FORMATS.get(path.suffix.lower())
            if format is None:
                raise AdaError("E_INVALID", f"The format of {path.name} is not known by its extension: say it.")
            content = path.read_bytes()
        body = _drop_none(format=format, mapping=None if mapping is None else dict(mapping), partial=partial, learn=learn)
        job = Job.of(self.ada._write("POST", self._path("/imports"), body))
        link = (job.upload or {}).get("url")
        if not link:
            raise AdaError("E_IMPORT", "The import answered no upload link.", 0, {"job": job.data})
        headers = {"content-type": "application/octet-stream", "accept": "application/json"}
        status, answered, got = self.ada._exchange("PUT", link, headers, content)
        job = Job.of(_parsed(status, answered, got))
        return self.ada.wait(job, timeout=timeout, on_progress=on_progress) if wait else job

    def export(
        self,
        *,
        format: str = "jsonl",  # noqa: A002  # the API's own name
        to: Optional[Union[str, "os.PathLike[str]"]] = None,
        wait: bool = True,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
    ) -> Job:
        """Everything of the model, as a job: `jsonl`, a zip of the precedents (as stored situations), every spec
        version and what was learned; or `ada_sqlite`, a kernel store. The done job's `download` is a one-hour link;
        `to` also writes the file there."""
        job = self._job("/export", {"format": format}, wait or to is not None, timeout, on_progress)
        if to is not None:
            Path(to).write_bytes(self.ada.download(job))
        return job

    # SDK 3.0's calls, through POST /v1/runs: each answers a Result, as it did

    def call(
        self,
        function: str = "start",
        inputs: Optional[Mapping[str, Any]] = None,
        *,
        version: Optional[int] = None,
        clearance: Optional[float] = None,
    ) -> Result:
        body: Dict[str, Any] = {"model": self.name, "function": function, "inputs": dict(inputs or {})}
        if version is not None:
            body["version"] = version
        if clearance is not None:
            body["clearance"] = clearance
        return _result(self.ada._call("POST", "/v1/runs", body, read=function in READS))

    def resume(self, run_id: str, answer: Any) -> Result:
        return self.ada.resume(run_id, answer)

    def record(
        self,
        data: Mapping[str, Any],
        outcome: Optional[str] = None,
        *,
        outcomes: Optional[Mapping[str, str]] = None,
        ts: Optional[float] = None,
    ) -> Result:
        """One case, with its outcome when known: `data` {id, precedents}."""
        inputs: Dict[str, Any] = {"data": dict(data), **_drop_none(outcome=outcome, ts=ts)}
        if outcomes is not None:
            inputs["outcomes"] = dict(outcomes)
        return self.call("record", inputs)

    def query(
        self, data: Mapping[str, Any], *, output: Optional[str] = None, clearance: Optional[float] = None
    ) -> Result:
        """The nearest precedents' vote: `data` {sufficient, confidence, support, count, top, outcomes, receipts}."""
        return self.call("query", {"data": dict(data), **_drop_none(output=output)}, clearance=clearance)

    def facts(
        self,
        data: Mapping[str, Any],
        *,
        top: Optional[int] = None,
        output: Optional[str] = None,
        clearance: Optional[float] = None,
    ) -> Result:
        """The nearest fact trees, best first, each cut to what the clearance may see."""
        return self.call("facts", {"data": dict(data), **_drop_none(top=top, output=output)}, clearance=clearance)

    def probabilities(
        self, data: Mapping[str, Any], *, output: Optional[str] = None, clearance: Optional[float] = None
    ) -> Result:
        """P(outcome | data), calibrated."""
        return self.call("probabilities", {"data": dict(data), **_drop_none(output=output)}, clearance=clearance)

    def learn(
        self,
        *,
        sample: Optional[int] = None,
        clearance: Optional[float] = None,
        timeout: float = JOB_TIMEOUT,
        on_progress: Optional[Progress] = None,
    ) -> Result:
        """The model weighs its roles from its own precedents and calibrates: `data` the roles' weights. A learn
        that outlasts the call's minute is waited for as the job it is (`learn_job` for the job itself)."""
        r = self.call("learn", {} if sample is None else {"sample": sample}, clearance=clearance)
        if isinstance(r.data, dict) and set(r.data) == {"job"} and isinstance(r.data["job"], dict):
            job = self.ada.wait(Job.of(r.data["job"]), timeout=timeout, on_progress=on_progress)
            return Result(r.run_id, r.model, r.version, r.function, r.status, job.result, r.step, r.prompt, r.seconds)
        return r
