"""One worker process: single-threaded (one message at a time, so the kernel needs no thread safety), holding one
Postgres connection, one Redis client and its model cache, serving one kernel (docs/specs/ada-cloud.md, 12.4). It
reads its kernel's own stream and, when that kernel is the latest stable's, the front door, where it passes each
message for another kernel's model to that kernel's stream. At start it brings every org schema to the latest shape;
it reconnects when its connection breaks, dropping its cache (the kernel's stores hold the old connection). The
latest stable's job workers also move the models of retired Ada versions (retirement.py), at start and hourly."""

import logging
import os
import socket
import threading
import time
from typing import Any

from redis import Redis

from glyphh_ada import files, jobs, orgschema, pg, registry, retirement, routing, runner
from glyphh_ada.backtest import Handoff
from glyphh_ada.cache import Models
from glyphh_ada.errors import Refusal
from glyphh_ada.handlers import Context, handle
from glyphh_ada.loop import Forwarded, Loop
from glyphh_ada.protocol import JOBS, STREAM_MAX, STREAMS, Message, kernel_stream
from glyphh_server.config import Settings
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")
SWEEP_EVERY: float = 3600.0  # seconds between two moves of retired versions' models


class Worker:
    def __init__(self, settings: Settings, queue: str, kernel: str | None = None) -> None:
        self.settings, self.queue = settings, queue
        self.kernel = kernel or routing.installed()
        self.front = self.kernel == registry.registry().latest(registry.today()).kernel
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=30)
        self.ctx = self._connect()
        consumer = f"{socket.gethostname()}-{os.getpid()}-{threading.get_ident()}"
        streams = [kernel_stream(queue, self.kernel)] + ([STREAMS[queue]] if self.front else [])
        self.loop = Loop(queue, self.redis, consumer, self.dispatch, streams)
        self.swept: float | None = None

    def _connect(self) -> Context:
        conn = pg.connect(self.settings.database_url)
        return Context(conn, self.redis, Models(conn, self.redis))

    def start(self) -> int:
        """The groups made, every org schema migrated; returns how many migrations ran."""
        self.loop.ensure_group()
        return orgschema.migrate_all(self.ctx.conn)

    def forward(self, kernel: str, msg: Message) -> None:
        """The message, unchanged, on its kernel's stream: that kernel's worker answers it."""
        routing.check(kernel)
        self.redis.xadd(kernel_stream(self.queue, kernel), msg.fields(), maxlen=STREAM_MAX, approximate=True)
        raise Forwarded

    def dispatch(self, msg: Message) -> tuple[Any, ...]:
        if self.ctx.conn.broken or self.ctx.conn.closed:
            log.warning("reconnecting to Postgres", extra=fields(queue=self.queue))
            self.ctx = self._connect()
        if self.queue == JOBS:
            work(self.ctx, msg, self)
            return None, None
        kernel, found = routing.for_message(self.ctx.conn, pg.enter(self.ctx.conn, msg.org), msg)
        if kernel is not None and kernel != self.kernel:
            self.forward(kernel, msg)
        data, version = handle(self.ctx, msg)
        return data, version, routing.about(found)

    def sweep(self) -> int:
        """The latest stable's job workers move retired versions' models, at start and then hourly. Returns how many
        moves it started."""
        due = self.swept is None or time.monotonic() - self.swept >= SWEEP_EVERY
        if not (self.queue == JOBS and self.front and due):
            return 0
        self.swept = time.monotonic()
        return retirement.sweep(self.ctx)

    def serve(self, stop: threading.Event) -> None:
        self.start()
        while not stop.is_set():
            self.sweep()
            self.loop.one()


def work(ctx: Context, msg: Message, worker: Worker) -> None:
    """One job, on its own kernel (else passed to that kernel's stream), its row moved through running to done or
    failed; the model's workers reload it after. Files no job needs any more go first."""
    schema = pg.enter(ctx.conn, msg.org)
    job_id = str(msg.args["job"])
    try:
        job = jobs.view(ctx.conn, schema, job_id)
        if job["state"] in ("done", "failed"):
            return
        kernel = routing.for_job(ctx.conn, schema, job)
    except Refusal:  # its model was deleted, and its jobs with it
        return
    if kernel != worker.kernel:
        try:
            worker.forward(kernel, msg)
        except Refusal as r:
            jobs.mark(ctx.conn, schema, job_id, "failed", error={"code": r.code, "message": r.message, **r.detail})
            return
    files.prune(ctx.conn, schema)
    jobs.mark(ctx.conn, schema, job_id, "running", percent=0)
    try:
        progress = lambda p: jobs.mark(ctx.conn, schema, job_id, "running", percent=round(p, 1))  # noqa: E731
        bump = lambda: ctx.models.bump(msg.org, msg.model)  # noqa: E731
        result = runner.run(ctx.conn, schema, job, progress, bump, worker.kernel)
    except Handoff as h:  # a backtest's candidates on another kernel: that kernel's job worker goes on with it
        jobs.mark(ctx.conn, schema, job_id, "queued", result=h.partial)
        ctx.redis.xadd(kernel_stream(JOBS, h.kernel), msg.fields(), maxlen=STREAM_MAX, approximate=True)
        return
    except Refusal as r:
        jobs.mark(ctx.conn, schema, job_id, "failed", error={"code": r.code, "message": r.message, **r.detail})
        log.warning("job refused: %s", job["kind"], extra=fields(org=msg.org, job=job_id, code=r.code))
        return
    except Exception:
        if not (ctx.conn.broken or ctx.conn.closed):
            jobs.mark(ctx.conn, schema, job_id, "failed", error={"code": "E_INTERNAL", "message": "The job failed."})
        raise
    jobs.mark(ctx.conn, schema, job_id, "done", percent=100, result=result)
    ctx.models.bump(msg.org, msg.model)
