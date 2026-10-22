"""What a worker does with one message: it enters the message's org (pg.enter), then reads, looks or writes, and
answers (data, the model's active spec version or None).

A write runs in one transaction with a row in the org's `requests` table, keyed by the caller's Idempotency-Key or the
message's id, holding the answer: a message taken again after its worker died, or a request sent again, gets the first
answer and writes nothing (the same key with another body: 409 E_IDEMPOTENCY). What must follow a commit (a version
bump, a job on its stream) runs after it."""

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from redis import Redis

from glyphh_ada import catalog, jobs, orgschema, pg, reads
from glyphh_ada.cache import Models
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.protocol import JOBS, STREAM_MAX, STREAMS, WRITES, Message
from glyphh_ada.writes import WRITERS

PRUNE_ONE_IN: int = 500  # one write in so many also deletes the org's request keys older than a day
Answer = tuple[Any, int | None]


@dataclass
class Context:
    conn: psycopg.Connection
    redis: Redis
    models: Models
    after: list[Callable[[], None]] = field(default_factory=list)


def handle(ctx: Context, msg: Message) -> Answer:
    schema = pg.enter(ctx.conn, msg.org)
    ctx.after.clear()
    answer = _once(ctx, schema, msg) if msg.op in WRITES else _look(ctx, schema, msg)
    for then in ctx.after:
        then()
    return answer


def _look(ctx: Context, schema: str, msg: Message) -> Answer:
    if msg.op == "models":
        return catalog.listing(ctx.conn, schema), None
    if msg.op == "model":
        found = catalog.view(ctx.conn, schema, msg.model)
        return found, found["version"]
    if msg.op == "job":
        return jobs.view(ctx.conn, schema, str(msg.args.get("id"))), None
    entry = ctx.models.get(msg.org, schema, msg.model)
    try:
        return reads.read(entry.model, msg.op, msg.args, msg.clearance), entry.version
    finally:
        ctx.models.settle(msg.org, msg.model, entry)


def _job(ctx: Context, schema: str, msg: Message) -> Answer:
    entry = ctx.models.get(msg.org, schema, msg.model)
    kind = msg.args["kind"]
    job_id = jobs.add(ctx.conn, schema, entry.model_id, kind, msg.args.get("args") or {}, msg.author)
    work = Message(msg.org, msg.model, kind, {"job": job_id}, author=msg.author)
    ctx.after.append(lambda: ctx.redis.xadd(STREAMS[JOBS], work.fields(), maxlen=STREAM_MAX, approximate=True))
    return jobs.view(ctx.conn, schema, job_id), entry.version


def _write(ctx: Context, schema: str, msg: Message) -> Answer:
    if msg.op == "create":
        ctx.after.append(lambda: ctx.models.bump(msg.org, msg.model))
        made = catalog.create(ctx.conn, msg.org, msg.model, msg.args["spec"], msg.author)
        return made, made["version"]
    if msg.op == "delete":
        catalog.delete(ctx.conn, schema, msg.model)
        ctx.after.append(lambda: ctx.models.bump(msg.org, msg.model))
        return {"name": msg.model, "deleted": True}, None
    if msg.op == "job_start":
        return _job(ctx, schema, msg)
    entry = ctx.models.get(msg.org, schema, msg.model)
    entry.model.space.author = msg.author
    return WRITERS[msg.op](entry.model, msg.args), entry.version


def _seen(ctx: Context, schema: str, key: str, body: str) -> Any:
    """The answer kept for this key, if a write with it committed; the same key with another body is refused."""
    ctx.conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{schema}:{key}",))
    found = ctx.conn.execute(q(schema, "SELECT body, reply FROM {s}.requests WHERE key = %s"), (key,)).fetchone()
    if found is not None and found[0] != body:
        raise Refusal("E_IDEMPOTENCY", "This Idempotency-Key was sent with another request.", 409)
    return found


def _once(ctx: Context, schema: str, msg: Message) -> Answer:
    body = hashlib.sha256(json.dumps([msg.op, msg.model, msg.args], sort_keys=True).encode()).hexdigest()
    with ctx.conn.transaction():
        if msg.op in ("create", "delete"):  # they change the schema's tables: one at a time per org, catalog fresh
            orgschema.lock(ctx.conn, schema, msg.org)
        found = _seen(ctx, schema, msg.once, body) if catalog.has(ctx.conn, schema, "requests") else None
        if found is not None:
            ctx.after.clear()
            return found[1]["data"], found[1]["version"]
        data, version = _write(ctx, schema, msg)
        kept = json.loads(json.dumps({"data": data, "version": version}, default=str))
        insert = "INSERT INTO {s}.requests (key, body, reply) VALUES (%s, %s, %s)"
        ctx.conn.execute(q(schema, insert), (msg.once, body, Jsonb(kept)))
        if random.randrange(PRUNE_ONE_IN) == 0:
            ctx.conn.execute(q(schema, "DELETE FROM {s}.requests WHERE at < now() - interval '1 day'"))
    return kept["data"], kept["version"]
