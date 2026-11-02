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

from glyphh_ada import catalog, dashboard, glyphmap, history, jobs, orgschema, pg, reads, seen, versions, writeops
from glyphh_ada.cache import Models
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal, model_missing
from glyphh_ada.protocol import CASES, VERSIONS, WRITES, Message

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
    try:
        answer = _once(ctx, schema, msg) if msg.op in WRITES else _look(ctx, schema, msg)
    except psycopg.errors.UndefinedTable:  # the org's schema went (the org was deleted) under a cached model
        ctx.models.drop_org(msg.org)
        raise model_missing(msg.model) from None
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
        return jobs.view(ctx.conn, schema, str(msg.args.get("id")), ctx.redis), None
    if msg.op == "job_cancel":
        return jobs.cancel(ctx.conn, schema, str(msg.args.get("id")), msg.author, ctx.redis), None
    if msg.op == "versions":
        if msg.args.get("levers"):
            levers = versions.levers(ctx.conn, schema, msg.model)
            return levers, levers["version"]
        if "against" in msg.args:  # what making the version active would change from another (None: the active)
            return history.compare(ctx.conn, schema, msg.model, int(msg.args["version"]), msg.args["against"]), None
        if "version" in msg.args:
            return history.detail(ctx.conn, schema, msg.model, int(msg.args["version"])), None
        return history.listing(ctx.conn, schema, msg.model), None
    if msg.op == "stats":
        found = dashboard.stats(ctx.conn, schema, msg.model)
        return found, found["version"]
    if msg.op == "precedent":
        live = catalog.live(ctx.conn, schema, msg.model)
        return seen.precedent(ctx.conn, schema, live, str(msg.args.get("id")), msg.clearance), live.version
    entry = ctx.models.get(msg.org, schema, msg.model)
    try:
        if msg.op == "map":
            return glyphmap.glyph_map(ctx.conn, schema, entry, msg.args, msg.clearance), entry.version
        # A read (protocol.READS): the same read of the model as it stands is this worker's answer of before.
        kept = ctx.models.answer(msg.org, msg.model, entry, msg.op, msg.args, msg.clearance)
        if kept is not None:
            return kept
        data = reads.read(entry.model, msg.op, msg.args, msg.clearance)
        ctx.models.keep(msg.org, msg.model, entry, msg.op, msg.args, msg.clearance, data)
        return data, entry.version
    finally:
        ctx.models.settle(msg.org, msg.model, entry)


def _write(ctx: Context, schema: str, msg: Message) -> Answer:
    if msg.op == "create":
        ctx.after.append(lambda: ctx.models.bump(msg.org, msg.model))
        made = catalog.create(ctx.conn, msg.org, msg.model, msg.args["spec"], msg.author, msg.args.get("ada"))
        return made, made["version"]
    if msg.op == "delete":
        catalog.delete(ctx.conn, schema, msg.model)
        ctx.after.append(lambda: ctx.models.bump(msg.org, msg.model))
        return {"name": msg.model, "deleted": True}, None
    if msg.op in CASES:
        return writeops.cases(ctx, schema, msg)
    if msg.op in VERSIONS:
        return writeops.version(ctx, schema, msg)
    if msg.op == "note":
        return versions.annotate(ctx.conn, schema, msg.model, int(msg.args["version"]), str(msg.args["note"])), None
    return {"job_start": writeops.job_start, "import_start": writeops.import_start, "import_go": writeops.import_go}[
        msg.op
    ](ctx, schema, msg)


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
