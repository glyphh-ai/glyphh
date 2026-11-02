"""A running job's life (2026-11-02: a learn showed 84.5% for 40 minutes, and no job could be stopped).

Its worker beats in Redis (protocol.job_beat_key) from a thread of its own (Beat) while the job runs, through the
kernel's long calls too. A running job whose beat is gone has lost its worker: another takes it up within
CLAIM_IDLE; one still without a beat STALL_SECONDS after it started is failed, E_JOB_STALLED, when it is looked at
(jobs.view). A job that stopped its worker MAX_DELIVERIES times is failed, E_JOB_LOST (process.lost).

Its progress (Tracker) writes its percent and stage (what it is doing now, with its counts) and hears a cancel: once
someone asked (jobs.cancel), the next step raises Cancelled, and the job is failed E_CANCELLED (failed, so a client
that waits for done or failed stops), its message saying what of its work stays."""

import logging
import threading
from collections.abc import Callable
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from redis import Redis
from redis.exceptions import RedisError

from glyphh_ada.catalog import q
from glyphh_ada.protocol import CLAIM_IDLE, HEARTBEAT, JOB_BEAT_TTL, JOBS, job_beat_key
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")
# A running job with no beat for this long has lost its worker and nobody took it again (CLAIM_IDLE, then a start).
STALL_SECONDS: int = JOB_BEAT_TTL + CLAIM_IDLE[JOBS] // 1000
LEARNED_AT: float = 60.0  # a learn's percent once the kernel has written the new weights (jobs._learn)

# What of a cancelled job's work stays, by its kind; a learn's by where it was stopped (kept).
KEPT: dict[str, str] = {
    "learn": "The model is as it was before this learn.",
    "calibrate": "The model keeps its temperature as it was.",
    "import": "The cases recorded before it stopped are kept; the rest of the file was not recorded.",
    "export": "Nothing was exported.",
    "reencode": "The model stays on its store as it was.",
    "backtest": "Nothing was scored; the model was not touched.",
}
LEARNED_KEPT: str = (
    "The model has its newly learned weights; the precedents not restated yet are restated by the next learn."
)
NOT_STARTED: str = "It had not started: nothing of it was done."
STALLED: dict[str, str] = {
    "code": "E_JOB_STALLED",
    "message": "This job's worker stopped and no other took it up: start it again.",
}
LOST: dict[str, str] = {
    "code": "E_JOB_LOST",
    "message": "This job stopped its worker three times and was given up: start it again, or ask support@glyphh.ai.",
}


class Cancelled(Exception):
    """Raised at a running job's progress once someone asked to cancel it."""

    def __init__(self, by: str) -> None:
        super().__init__(by)
        self.by = by


def kept(kind: str, percent: float) -> str:
    return LEARNED_KEPT if kind == "learn" and percent >= LEARNED_AT else KEPT[kind]


def cancelled(by: str, what_stays: str) -> dict[str, str]:
    return {"code": "E_CANCELLED", "message": f"Cancelled by {by}. {what_stays}", "by": by}


def gone_error(kind: str, percent: float, cancel_by: str | None) -> dict[str, str]:
    """A running job that lost its worker: stalled, or cancelled when someone had asked."""
    return cancelled(cancel_by, kept(kind, percent)) if cancel_by else STALLED


def beat(redis: Redis, job_id: str) -> None:
    redis.set(job_beat_key(job_id), "1", ex=JOB_BEAT_TTL)


def beating(redis: Redis, job_id: str) -> bool:
    return bool(redis.exists(job_beat_key(job_id)))


def fail_open(conn: psycopg.Connection, schema: str, job_id: str, error: dict[str, Any]) -> None:
    """Failed with this error, if it is still open (a worker may have just finished it)."""
    text = (
        "UPDATE {s}.jobs SET state = 'failed', error = %s, stage = NULL, finished_at = now() "
        "WHERE id = %s AND state IN ('awaiting', 'queued', 'running')"
    )
    conn.execute(q(schema, text), (Jsonb(error), job_id))


class Beat:
    """A running job's beat, every HEARTBEAT[JOBS] seconds from a thread of its own; it expires with its worker."""

    def __init__(self, redis: Redis, job_id: str) -> None:
        self.redis, self.job_id, self.stop = redis, job_id, threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while True:
            try:
                beat(self.redis, self.job_id)
            except RedisError:  # a beat lost to Redis is tried again at the next
                log.warning("a job's beat failed", extra=fields(job=self.job_id))
            if self.stop.wait(HEARTBEAT[JOBS]):
                return

    def __enter__(self) -> "Beat":
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.thread.join()


class Tracker:
    """A running job's progress: its percent and stage written as it goes, its beat kept, and its cancel heard (each
    call raises Cancelled once someone asked). `on_change` runs after each step: one may have changed the model's
    precedents (a batch restated or imported)."""

    def __init__(
        self, conn: psycopg.Connection, schema: str, job_id: str, redis: Redis, on_change: Callable[[], None]
    ) -> None:
        self.conn, self.schema, self.job_id, self.redis, self.on_change = conn, schema, job_id, redis, on_change
        self.percent = 0.0

    def __call__(self, percent: float, stage: str | None = None) -> None:
        self.percent = round(percent, 1)
        text = "UPDATE {s}.jobs SET percent = %s, stage = coalesce(%s, stage) WHERE id = %s RETURNING cancel_by"
        row = self.conn.execute(q(self.schema, text), (self.percent, stage, self.job_id)).fetchone()
        beat(self.redis, self.job_id)
        self.on_change()
        if row is not None and row[0]:
            raise Cancelled(row[0])
