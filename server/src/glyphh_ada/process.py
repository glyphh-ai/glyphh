"""One worker process: single-threaded (one message at a time, so the kernel needs no thread safety), holding one
Postgres connection, one Redis client and its model cache. At start it brings every org schema to the latest shape;
it reconnects when its connection breaks, dropping its cache (the kernel's stores hold the old connection)."""

import logging
import os
import socket
import threading
from typing import Any

from redis import Redis

from glyphh_ada import files, jobs, orgschema, pg, runner
from glyphh_ada.cache import Models
from glyphh_ada.errors import Refusal
from glyphh_ada.handlers import Context, handle
from glyphh_ada.loop import Loop
from glyphh_ada.protocol import JOBS, Message
from glyphh_server.config import Settings
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")


class Worker:
    def __init__(self, settings: Settings, queue: str) -> None:
        self.settings, self.queue = settings, queue
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=30)
        self.ctx = self._connect()
        consumer = f"{socket.gethostname()}-{os.getpid()}-{threading.get_ident()}"
        self.loop = Loop(queue, self.redis, consumer, self.dispatch)

    def _connect(self) -> Context:
        conn = pg.connect(self.settings.database_url)
        return Context(conn, self.redis, Models(conn, self.redis))

    def start(self) -> int:
        """The group made, every org schema migrated; returns how many migrations ran."""
        self.loop.ensure_group()
        return orgschema.migrate_all(self.ctx.conn)

    def dispatch(self, msg: Message) -> tuple[Any, int | None]:
        if self.ctx.conn.broken or self.ctx.conn.closed:
            log.warning("reconnecting to Postgres", extra=fields(queue=self.queue))
            self.ctx = self._connect()
        if self.queue == JOBS:
            work(self.ctx, msg)
            return None, None
        return handle(self.ctx, msg)

    def serve(self, stop: threading.Event) -> None:
        self.start()
        while not stop.is_set():
            self.loop.one()


def work(ctx: Context, msg: Message) -> None:
    """One job, its row moved through running to done or failed; the model's workers reload it after. Files no job
    needs any more go first."""
    schema = pg.enter(ctx.conn, msg.org)
    job_id = str(msg.args["job"])
    try:
        job = jobs.view(ctx.conn, schema, job_id)
    except Refusal:  # its model was deleted, and its jobs with it
        return
    if job["state"] in ("done", "failed"):
        return
    files.prune(ctx.conn, schema)
    jobs.mark(ctx.conn, schema, job_id, "running", percent=0)
    try:
        progress = lambda p: jobs.mark(ctx.conn, schema, job_id, "running", percent=round(p, 1))  # noqa: E731
        result = runner.run(ctx.conn, schema, job, progress, lambda: ctx.models.bump(msg.org, msg.model))
    except Refusal as r:
        jobs.mark(ctx.conn, schema, job_id, "failed", error={"code": r.code, "message": r.message, **r.detail})
        return
    except Exception:
        if not (ctx.conn.broken or ctx.conn.closed):
            jobs.mark(ctx.conn, schema, job_id, "failed", error={"code": "E_INTERNAL", "message": "The job failed."})
        raise
    jobs.mark(ctx.conn, schema, job_id, "done", percent=100, result=result)
    ctx.models.bump(msg.org, msg.model)
