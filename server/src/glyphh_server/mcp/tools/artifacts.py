"""The connector's artifact tools (docs/specs/artifacts.md, 3.5): the org's artifacts as cards (the artifacts panel
shows them), and a reviewer's approve, reject and retire."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops import artifacts
from glyphh_server.ops.artifacts import PER_PAGE, PER_PAGE_MAX, REASON_MAX, ArtifactView

ARTIFACTS_URI: str = "ui://glyphh/artifacts/1"


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(None, max_length=200, description="Matches the title, description and name")
    page: int = Field(1, ge=1)
    per_page: int = Field(PER_PAGE, ge=1, le=PER_PAGE_MAX)
    state: Literal["draft", "approved", "rejected", "retired"] = Field(
        "approved", description="draft, rejected and retired are the reviewers' to see"
    )


class ArtifactId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: uuid.UUID


class Rejection(ArtifactId):
    reason: str = Field(min_length=1, max_length=REASON_MAX, description="Why, for whoever published it")


def _line(a: ArtifactView) -> str:
    who = a.submitted_by.name or a.submitted_by.email if a.submitted_by else "a deploy"
    return f"{a.title} v{a.version} on {a.runtime_name}, {a.state}, by {who}: {a.url} (id {a.id})"


async def list_artifacts(ctx: Context, args: Listing) -> Done:
    page = await artifacts.list_artifacts(ctx.conn, ctx.who, args.q, args.page, args.per_page, args.state)
    lines = [_line(a) for a in page.artifacts]
    head = f"{page.total} {args.state} artifact{'' if page.total == 1 else 's'}, page {page.page}."
    return Done("\n".join([head, *lines]) if lines else f"No {args.state} artifacts.", dump(page))


async def approve(ctx: Context, args: ArtifactId) -> Done:
    done = await artifacts.approve(ctx.conn, ctx.hub, ctx.who, args.artifact_id)
    return Done(f"{done.title} v{done.version} is approved: {done.url}", dump(done))


async def reject(ctx: Context, args: Rejection) -> Done:
    done = await artifacts.reject(ctx.conn, ctx.hub, ctx.who, args.artifact_id, args.reason)
    return Done(f"{done.title} v{done.version} is rejected: {done.reason}", dump(done))


async def retire(ctx: Context, args: ArtifactId) -> Done:
    done = await artifacts.retire(ctx.conn, ctx.hub, ctx.who, args.artifact_id)
    return Done(f"{done.title} is retired.", dump(done))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "artifacts",
        "Artifacts",
        "The org's artifacts (Claude's pages published to its rrotors): the approved ones your roles allow, as cards "
        "with Open; a reviewer sees drafts awaiting review (state draft), rejected and retired ones too. Search "
        "with q, page through with page.",
        Listing,
        list_artifacts,
        True,
        True,
        ARTIFACTS_URI,
    ),
    Tool(
        "artifact_approve",
        "Approve an artifact",
        "Approve a draft (or a rejected) artifact: its rrotor serves it from here on. The org's admin or a reviewer.",
        ArtifactId,
        approve,
        False,
        True,
        ARTIFACTS_URI,
    ),
    Tool(
        "artifact_reject",
        "Reject an artifact",
        "Reject a draft (or an approved) artifact with a reason for whoever published it. A reviewer's.",
        Rejection,
        reject,
        False,
        True,
        ARTIFACTS_URI,
    ),
    Tool(
        "artifact_retire",
        "Retire an artifact",
        "Retire an artifact: no longer served or listed. A reviewer's.",
        ArtifactId,
        retire,
        False,
        True,
        ARTIFACTS_URI,
    ),
)
