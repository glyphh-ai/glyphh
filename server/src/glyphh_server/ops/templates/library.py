"""The template library (docs/specs/templates.md): what a template is, the ones Glyphh ships (library/*.json, read
once), and seeding them into `templates` at every start, a new version replacing the row. A template is a bundle a
person installs for themselves: Ada models made from one spec, the tools it adds to that person's connector (each one
of the ops in ops/templates/glyphh.py over those models), what a hook puts in an AI's context, and the instructions an
AI without hooks follows. A template no longer shipped is retired, never deleted: its installs keep working."""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Template

LIBRARY: Path = Path(__file__).with_name("library")
KEY: str = r"^[a-z][a-z0-9_]{0,15}$"
Op = Literal["remember", "recall", "list", "forget"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelPart(Strict):
    key: str = Field(pattern=KEY)
    title: str
    about: str


class ToolPart(Strict):
    name: str = Field(pattern=r"^glyphh_[a-z_]{1,40}$")
    title: str
    op: Op
    description: str
    kinds: list[str] | None = None  # the models it works over; None: every one of the template's


class Pull(Strict):
    kind: str
    top: int = Field(ge=1, le=50)


class ContextPart(Strict):
    session: list[Pull] = []  # what a session's start gets: each kind's newest
    prompt: list[Pull] = []  # what each prompt gets: each kind's closest to it


class Body(Strict):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    name: str
    category: str
    version: int = Field(ge=1)
    summary: str
    spec: dict[str, Any]
    models: list[ModelPart] = Field(min_length=1)
    tools: list[ToolPart] = Field(min_length=1)
    context: ContextPart = ContextPart()
    instructions: str

    def kinds(self, tool: ToolPart) -> list[str]:
        return tool.kinds or [m.key for m in self.models]


def shipped() -> tuple[Body, ...]:
    """Every template Glyphh ships, by slug."""
    return tuple(Body.model_validate(json.loads(p.read_text())) for p in sorted(LIBRARY.glob("*.json")))


SHIPPED: tuple[Body, ...] = shipped()


async def seed_templates(conn: AsyncConnection) -> None:
    for sort, body in enumerate(SHIPPED):
        row = {
            "name": body.name,
            "category": body.category,
            "summary": body.summary,
            "version": body.version,
            "body": body.model_dump(mode="json"),
            "active": True,
            "sort": sort,
        }
        await conn.execute(
            upsert(Template)
            .values(slug=body.slug, **row)
            .on_conflict_do_update(index_elements=[Template.slug], set_=row, where=Template.version <= body.version)
        )
    await conn.execute(update(Template).where(Template.slug.not_in([b.slug for b in SHIPPED])).values(active=False))
