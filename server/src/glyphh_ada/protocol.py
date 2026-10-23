"""The messages between the API and the workers, on the server's Redis: two streams read by consumer groups, a reply
list per synchronous request, and a version counter per model that tells a worker its cached model is stale.

A message is a flat Redis hash: `id`, `org`, `model`, `op`, `args` (JSON), `clearance`, `author`, `deadline` (epoch
seconds; a worker that takes it later drops it), `key` (an Idempotency-Key, or the id) and `cap` (the precedents the
org's plan allows across its models; empty for no cap). The worker answers a sync
message by LPUSHing `{"ok": true, "data": ..., "version": ...}` or `{"ok": false, "error": {...}}` to its reply
list, which expires."""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

SYNC, JOBS = "sync", "jobs"
STREAMS: dict[str, str] = {SYNC: "ada:sync", JOBS: "ada:jobs"}
GROUP: str = "ada"
STREAM_MAX: int = 100_000  # each stream is trimmed to about this many entries
REPLY_TTL: int = 60  # seconds a reply waits for the API to read it
# A message a worker took and stopped heartbeating for this long is claimed by another (XAUTOCLAIM), in ms.
CLAIM_IDLE: dict[str, int] = {SYNC: 5_000, JOBS: 60_000}
HEARTBEAT: dict[str, float] = {SYNC: 1.0, JOBS: 10.0}
MAX_DELIVERIES: int = 3  # a message that killed this many workers is answered E_INTERNAL and dropped

READS: frozenset[str] = frozenset({"query", "probabilities", "facts", "decide"})
# The writes to a model's precedents, each under the model's write lock (versions.write_lock)
CASES: frozenset[str] = frozenset({"record", "record_many", "grade", "forget"})
# A new version, another made active, or the active spec on another Ada version (upgrade)
VERSIONS: frozenset[str] = frozenset({"spec", "settings", "activate", "upgrade"})
# note: a version's note written again
WRITES: frozenset[str] = (
    frozenset({"create", "delete", "job_start", "import_start", "import_go", "note"}) | CASES | VERSIONS
)
LOOKS: frozenset[str] = frozenset({"models", "model", "job", "versions", "stats", "map", "precedent"})
SYNC_OPS: frozenset[str] = READS | WRITES | LOOKS
JOB_KINDS: frozenset[str] = frozenset({"learn", "calibrate", "import", "export", "reencode", "backtest"})
# What any worker answers, whatever kernel the model runs: no kernel reads or writes the model's cases or spec
ANY_KERNEL: frozenset[str] = frozenset({"models", "model", "job", "note", "delete", "activate", "upgrade"})


def kernel_stream(queue: str, kernel: str) -> str:
    """The stream of one kernel's workers (docs/specs/ada-cloud.md, 12.4): `ada:sync:3.12.2`, `ada:jobs:3.13.0`."""
    return f"{STREAMS[queue]}:{kernel}"


def reply_key(request_id: str) -> str:
    return f"ada:reply:{request_id}"


def version_key(org: str, name: str) -> str:
    """Bumped by every write that changes what a worker caches of a model: made, deleted, learned, calibrated, a
    version made active, an import ended."""
    return f"ada:ver:{org}:{name}"


@dataclass(frozen=True)
class Message:
    org: str
    model: str
    op: str
    args: dict[str, Any] = field(default_factory=dict)
    clearance: float = 1.0
    author: str = "anon"
    deadline: float = 0.0
    key: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cap: int | None = None

    def fields(self) -> dict[str, str]:
        out = {k: str(v) for k, v in asdict(self).items()}
        out["args"] = json.dumps(self.args, separators=(",", ":"))
        out["cap"] = "" if self.cap is None else str(self.cap)
        return out

    @classmethod
    def of(cls, raw: dict[str, str]) -> "Message":
        return cls(
            org=raw["org"],
            model=raw["model"],
            op=raw["op"],
            args=json.loads(raw["args"]),
            clearance=float(raw["clearance"]),
            author=raw["author"],
            deadline=float(raw["deadline"]),
            key=raw["key"],
            id=raw["id"],
            cap=int(raw["cap"]) if raw.get("cap") else None,
        )

    @property
    def expired(self) -> bool:
        return 0 < self.deadline < time.time()

    @property
    def once(self) -> str:
        """What makes a write happen once: the caller's Idempotency-Key, else the message's own id."""
        return self.key or self.id


def ok(data: Any, version: int | None = None, ada: dict[str, Any] | None = None) -> str:
    """An answer; `version` is the model's active spec version when the answer came from a model, `ada` its Ada
    version and what the caller should be told of it ({name, notice}), for the API's headers."""
    out = {"ok": True, "data": data, "version": version} | ({"ada": ada} if ada else {})
    return json.dumps(out, separators=(",", ":"), default=str)


def refused(code: str, message: str, status: int, **detail: Any) -> str:
    error = {"code": code, "message": message, "status": status, **detail}
    return json.dumps({"ok": False, "error": error}, separators=(",", ":"), default=str)
