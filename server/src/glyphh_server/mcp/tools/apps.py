"""The connector's app tools (docs/specs/apps.md, 3.5): the org's apps as cards (the apps panel shows them), and a
reviewer's approve, reject and retire."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.ops import apps
from glyphh_server.ops.apps import PER_PAGE, PER_PAGE_MAX, REASON_MAX, AppView

APPS_URI: str = "ui://glyphh/apps/1"


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(None, max_length=200, description="Matches the title, description and name")
    page: int = Field(1, ge=1)
    per_page: int = Field(PER_PAGE, ge=1, le=PER_PAGE_MAX)
    state: Literal["draft", "approved", "rejected", "retired"] = Field(
        "approved", description="draft, rejected and retired are the reviewers' to see"
    )
    type: Literal["page", "dashboard", "doc", "diagram", "deck", "design"] | None = Field(
        None, description="Only apps of this type; absent, every type"
    )


class AppId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: uuid.UUID


class Rejection(AppId):
    reason: str = Field(min_length=1, max_length=REASON_MAX, description="Why, for whoever published it")


def _line(a: AppView) -> str:
    who = a.submitted_by.name or a.submitted_by.email if a.submitted_by else "a deploy"
    return f"{a.title} ({a.type}) v{a.version} on {a.runtime_name}, {a.state}, by {who}: {a.url} (id {a.id})"


async def list_apps(ctx: Context, args: Listing) -> Done:
    page = await apps.list_apps(ctx.conn, ctx.who, args.q, args.page, args.per_page, args.state, args.type)
    lines = [_line(a) for a in page.apps]
    head = f"{page.total} {args.state} app{'' if page.total == 1 else 's'}, page {page.page}."
    return Done("\n".join([head, *lines]) if lines else f"No {args.state} apps.", dump(page))


async def approve(ctx: Context, args: AppId) -> Done:
    done = await apps.approve(ctx.conn, ctx.hub, ctx.who, args.app_id)
    return Done(f"{done.title} v{done.version} is approved: {done.url}", dump(done))


async def reject(ctx: Context, args: Rejection) -> Done:
    done = await apps.reject(ctx.conn, ctx.hub, ctx.who, args.app_id, args.reason)
    return Done(f"{done.title} v{done.version} is rejected: {done.reason}", dump(done))


async def retire(ctx: Context, args: AppId) -> Done:
    done = await apps.retire(ctx.conn, ctx.hub, ctx.who, args.app_id)
    return Done(f"{done.title} is retired.", dump(done))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "apps",
        "Apps",
        "The org's apps (what Claude made, published to its rrotors: pages, dashboards, docs, diagrams, decks, "
        "designs): the approved ones your roles allow, as cards with Open; a reviewer sees drafts awaiting review "
        "(state draft), rejected and retired ones too. Search with q, keep one type with type, page through with "
        "page.",
        Listing,
        list_apps,
        True,
        True,
        APPS_URI,
    ),
    Tool(
        "app_approve",
        "Approve an app",
        "Approve a draft (or a rejected) app: its rrotor serves it from here on. The org's admin or a reviewer.",
        AppId,
        approve,
        False,
        True,
        APPS_URI,
    ),
    Tool(
        "app_reject",
        "Reject an app",
        "Reject a draft (or an approved) app with a reason for whoever published it. A reviewer's.",
        Rejection,
        reject,
        False,
        True,
        APPS_URI,
    ),
    Tool(
        "app_retire",
        "Retire an app",
        "Retire an app: no longer served or listed. A reviewer's.",
        AppId,
        retire,
        False,
        True,
        APPS_URI,
    ),
)
