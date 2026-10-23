"""The writes a worker answers besides making and deleting a model (handlers.py runs each in its transaction, kept
under the request's key):

- a model's cases (record, record_many, grade, forget), under the model's write lock held shared (a re-encode's
  switch holds it alone, versions.write_lock), within the org's cap on precedents, starting a learn job when a write
  passes a multiple of the model's refresh_every;
- a job started (learn, calibrate, export, backtest), and an import: made waiting for its file (import_start), then
  queued when the file is in (import_go);
- a new version from a spec or from changed settings, and another version made active (versions.py)."""

from typing import Any

from glyphh_ada import jobs, routing, versions
from glyphh_ada.catalog import live
from glyphh_ada.errors import Refusal
from glyphh_ada.pg import schema_for
from glyphh_ada.protocol import JOBS, STREAM_MAX, Message, kernel_stream
from glyphh_ada.writes import WRITERS, refresh_due, within_cap

Answer = tuple[Any, int | None]


def enqueue(ctx: Any, msg: Message, kind: str, job_id: str) -> None:
    """The job on its kernel's jobs stream (routing.for_job), once the transaction that made it commits."""
    work = Message(msg.org, msg.model, kind, {"job": job_id}, author=msg.author)
    stream = kernel_stream(
        JOBS, routing.for_job(ctx.conn, schema_for(msg.org), jobs.view(ctx.conn, schema_for(msg.org), job_id))
    )
    ctx.after.append(lambda: ctx.redis.xadd(stream, work.fields(), maxlen=STREAM_MAX, approximate=True))


def cases(ctx: Any, schema: str, msg: Message) -> Answer:
    ctx.conn.execute("SELECT pg_advisory_xact_lock_shared(hashtext(%s))", (versions.write_lock(schema, msg.model),))
    entry = ctx.models.get(msg.org, schema, msg.model)
    entry.model.space.author = msg.author
    if msg.op in ("record", "record_many"):
        within_cap(ctx.conn, schema, entry.model, msg.args.get("cases") or [msg.args], msg.cap)
    answer = WRITERS[msg.op](entry.model, msg.args)
    if refresh_due(entry.model, msg.op, answer) and not jobs.open_of(ctx.conn, schema, entry.model_id, ["learn"]):
        enqueue(ctx, msg, "learn", jobs.add(ctx.conn, schema, entry.model_id, "learn", {"refresh": True}, msg.author))
    return answer, entry.version


def job_start(ctx: Any, schema: str, msg: Message) -> Answer:
    found = live(ctx.conn, schema, msg.model)
    kind = msg.args["kind"]
    job_id = jobs.add(ctx.conn, schema, found.id, kind, msg.args.get("args") or {}, msg.author)
    enqueue(ctx, msg, kind, job_id)
    return jobs.view(ctx.conn, schema, job_id), found.version


def import_start(ctx: Any, schema: str, msg: Message) -> Answer:
    """An import waiting for its file; refused while another import or a re-encode is open on the model."""
    found = live(ctx.conn, schema, msg.model)
    jobs.busy(ctx.conn, schema, found.id)
    args = {**msg.args, "cap": msg.cap}
    job_id = jobs.add(ctx.conn, schema, found.id, "import", args, msg.author, state="awaiting")
    return jobs.view(ctx.conn, schema, job_id), found.version


def import_go(ctx: Any, schema: str, msg: Message) -> Answer:
    """The import's file is in: queued (once; another time it is answered as it stands)."""
    job = jobs.view(ctx.conn, schema, str(msg.args["job"]))
    if job["kind"] != "import" or job["model"] != msg.model:
        raise Refusal("E_JOB_MISSING", "No such import.", 404)
    if job["state"] == "awaiting":
        jobs.mark(ctx.conn, schema, str(job["id"]), "queued")
        enqueue(ctx, msg, "import", str(job["id"]))
        job["state"] = "queued"
    return job, None


def version(ctx: Any, schema: str, msg: Message) -> Answer:
    """spec, settings, activate or upgrade: the answer {version, active, job}, the job queued, every worker's copy
    stale."""
    args = {**msg.args, "author": msg.author}
    if msg.op == "spec":
        made = versions.propose(ctx.conn, schema, msg.model, msg.args["spec"], args)
    elif msg.op == "settings":
        made = versions.settings(ctx.conn, schema, msg.model, msg.args["changes"], args)
    elif msg.op == "upgrade":
        made = versions.upgrade(ctx.conn, schema, msg.model, msg.args.get("ada"), args)
    else:
        made = versions.activate(ctx.conn, schema, msg.model, int(msg.args["version"]), msg.author)
    if made["job"] is not None:
        enqueue(ctx, msg, jobs.view(ctx.conn, schema, made["job"])["kind"], made["job"])
        made["job"] = jobs.view(ctx.conn, schema, made["job"])
    ctx.after.append(lambda: ctx.models.bump(msg.org, msg.model))
    return made, live(ctx.conn, schema, msg.model).version
