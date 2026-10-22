"""The connector's Ada job tools: learning and calibrating, backtesting candidates before a change goes live, importing
a file (by a one-hour upload link Claude's environment can PUT the file to, or the file or its rows inline) and
exporting a model (a one-hour download link once done); and any job's state and progress, waited on for a while."""

import asyncio
import json
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada.api.call import send
from glyphh_ada.api.imports import MAPPING, Format, begin
from glyphh_ada.api.jobs import NewExport, with_link
from glyphh_ada.api.tuning import NewBacktest
from glyphh_ada.errors import BadRequest
from glyphh_server.mcp.tools.ada_base import IDEMPOTENCY, NAME, Named, ada, caller, pct
from glyphh_server.mcp.tools.base import Context, Done, Tool

POLL: float = 0.5
WAIT_MAX: int = 50


class Backtest(NewBacktest):
    name: str = NAME


class Import(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = NAME
    format: Format = Field(description="JSON Lines, CSV, or a kernel SQLite store (ada_sqlite)")
    mapping: dict[str, str | None] | None = Field(None, description=MAPPING)
    partial: bool = Field(False, description="Past the plan's cap, record new cases up to it and refuse the rest")
    learn: bool = Field(True, description="Learn and calibrate once at the end")
    content: str | None = Field(None, description="The file itself, as text, when small (5 MB); else leave out")
    rows: list[dict[str, Any]] | None = Field(None, description="Or the cases themselves, {data, outcome?, ...} each")
    idempotency_key: str | None = IDEMPOTENCY


class Export(Named, NewExport):
    pass


class JobArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64, description="The job's id")
    wait_seconds: int = Field(0, ge=0, le=WAIT_MAX, description="Wait up to this long for it to end")


def said(job: dict[str, Any]) -> str:
    """A job in a line or two: its state, then what it found or why it failed."""
    line = f"Job {job['id']} ({job['kind']} of {job['model']}): {job['state']}, {job['percent']:.0f}%."
    if job["state"] == "failed":
        return f"{line} {job['error'].get('message', '')}".rstrip()
    if job.get("download"):
        return f"{line} Download (one hour): {job['download']['url']}"
    if job["state"] == "done" and job["kind"] == "backtest":
        result = job["result"]
        return "\n".join([line, _scored(result["active"]), *(_scored(c) for c in result["candidates"])])
    return line


def _scored(c: dict[str, Any]) -> str:
    named = c["candidate"].get("name") or json.dumps({k: v for k, v in c["candidate"].items() if k != "name"})
    if "error" in c:
        return f"{named}: {c['error']['message']}"
    cost = f", cost {c['cost']:g}" if "cost" in c else ""
    return f"{named}: accuracy {pct(c['accuracy'])}, asks {pct(c['ask_rate'])}{cost}"


async def _job(ctx: Context, name: str, kind: str, args: dict[str, Any] | None = None) -> Done:
    job, _v = await ada(ctx, name, "job_start", {"kind": kind, "args": args or {}})
    return Done(f"{said(job)} ada_job {job['id']} follows it.", job)


async def learn(ctx: Context, args: Named) -> Done:
    return await _job(ctx, args.name, "learn")


async def calibrate(ctx: Context, args: Named) -> Done:
    return await _job(ctx, args.name, "calibrate")


async def backtest(ctx: Context, args: Backtest) -> Done:
    body = args.model_dump(exclude_none=True, exclude={"name"})
    body["candidates"] = [c.model_dump(exclude_none=True) for c in args.candidates]
    return await _job(ctx, args.name, "backtest", body)


async def export(ctx: Context, args: Export) -> Done:
    return await _job(ctx, args.name, "export", {"format": args.format})


def _file(args: Import) -> bytes | None:
    if args.rows is None:
        return None if args.content is None else args.content.encode()
    if args.format != "jsonl" or args.content is not None:
        raise BadRequest("rows are JSON Lines cases: format jsonl, and no content beside them.", reason="rows")
    return "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in args.rows).encode()


async def start_import(ctx: Context, args: Import) -> Done:
    data = _file(args)
    opts = args.model_dump(include={"format", "mapping", "partial", "learn"}, exclude_none=True)
    who = await caller(ctx)
    job = await begin(ctx.ada, who, args.name, opts, data, ctx.settings.ada_base, args.idempotency_key or "")
    if "upload" not in job:
        return Done(f"{said(job)} ada_job {job['id']} follows it.", job)
    up = job["upload"]["url"]
    text = f"Import job {job['id']} waits for its file: PUT it within an hour, `curl -T <file> '{up}'`, then ada_job."
    return Done(text, job)


async def job(ctx: Context, args: JobArgs) -> Done:
    """The job, looked at again every POLL seconds while it runs, for up to wait_seconds. The caller is resolved once:
    the wait makes no statement on the request's own connection, so its transaction holds no snapshot that an
    import's concurrent index build would wait out."""
    who, deadline = await caller(ctx), time.monotonic() + args.wait_seconds
    found, _v = await send(ctx.ada, who, "", "job", {"id": args.id})
    while found["state"] not in ("done", "failed") and time.monotonic() < deadline:
        await asyncio.sleep(POLL)
        found, _v = await send(ctx.ada, who, "", "job", {"id": args.id})
    found = with_link(ctx.settings.ada_base, ctx.settings.secret_key, who, found)
    return Done(said(found), found)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "ada_learn",
        "Ada learn",
        "Learn each role's, value's, word's and pair's weight from the model's graded precedents, then calibrate: a "
        "job (ada_job).",
        Named,
        learn,
    ),
    Tool("ada_calibrate", "Ada calibrate", "Fit the probabilities' temperature alone: a job.", Named, calibrate),
    Tool(
        "ada_backtest",
        "Ada backtest",
        "Score the active version and up to ten candidates ({settings}, {spec_version} or {spec}) on the model's own "
        "held-out precedents (the newest 200 by default), never touching the live model: accuracy, log-loss, cost, "
        "ask rate and the change against the active version. A job (ada_job).",
        Backtest,
        backtest,
    ),
    Tool(
        "ada_import",
        "Ada import",
        "Load history into a model as a job: answers a one-hour upload link to PUT the file to (curl -T), or with the "
        "file's text (content) or its cases (rows) inline, up to 5 MB, the job queued at once. CSV maps headers to "
        "role paths and outcome columns. Learns once at the end.",
        Import,
        start_import,
    ),
    Tool(
        "ada_export",
        "Ada export",
        "Everything of a model (precedents, every spec version, what it learned) as a job; once done, ada_job answers "
        "a one-hour download link.",
        Export,
        export,
    ),
    Tool(
        "ada_job",
        "Ada job",
        "A job's state and progress (awaiting its file, queued, running, done, failed) and its result; waits up to "
        "wait_seconds for it to end; a done export's download link.",
        JobArgs,
        job,
        True,
    ),
)
