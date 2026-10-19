"""The connector's `logs` tool: the org's runtimes' recent log records, or their audit events, as server-side logging
brought them (rrotor's RROTOR_SERVER_LOGS=on), newest first."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops.telemetry import records
from glyphh_server.ops.telemetry.records import Ask, Level

OFF: str = (
    "Nothing sent yet. A runtime sends its logs here only with server-side logging on: RROTOR_SERVER_LOGS=on on the "
    "rrotor (its logs then leave your infrastructure); kept {days} days."
)


class Recent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit: bool = Field(False, description="The audit events (who did what) instead of the log records")
    runtime_id: uuid.UUID | None = Field(None, description="One runtime's only")
    level: Level | None = Field(None, description="Log records: this level and above")
    text: str | None = Field(None, max_length=200, description="Log records: in the message")
    limit: int = Field(20, ge=1, le=100, description="How many, newest first")


def _when(at: object) -> str:
    return f"{at:%Y-%m-%d %H:%M:%S}"


async def recent(ctx: Context, args: Recent) -> Done:
    ask = Ask(runtime=args.runtime_id, limit=args.limit, level=args.level, text=args.text)
    if args.audit:
        events = await records.audit(ctx.conn, ctx.who.org_id, ask)
        lines = [f"{_when(e.at)} {e.runtime or e.runtime_id}/{e.node_id or '-'} {e.kind}" for e in events.events]
        data = dump(events)
    else:
        logs = await records.logs(ctx.conn, ctx.who.org_id, ask)
        lines = [
            f"{_when(r.at)} {r.runtime or r.runtime_id}/{r.node_id or '-'} {r.level}: {r.body}" for r in logs.records
        ]
        data = dump(logs)
    if not lines:
        return Done(OFF.format(days=ctx.settings.telemetry_retention_days), data)
    return Done("Newest first, times UTC:\n" + "\n".join(lines), data)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "logs",
        "Runtime logs",
        "Your org's runtimes' recent log records (or, with audit, their audit events), newest first, as sent with "
        "server-side logging on (RROTOR_SERVER_LOGS=on); filter by runtime_id, level and text.",
        Recent,
        recent,
        True,
    ),
)
