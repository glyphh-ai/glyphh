"""The closeness card (mcp/panel.py, `ui://glyphh/closeness/1`). The Resume Screener plugin
(github.com/glyphh-ai/plugins, plugins/resume-screener) checks a resume and a cover letter against the person's own
`closeness` Ada model: how alike the nearest fake and the nearest real one are, and Ada's own decision with its
confidence and its fact tree. A plugin cannot show a panel, so it hands what its check printed to
`screener_closeness`, which answers it unchanged for the card to draw. The tool decides nothing, reads nothing and
keeps nothing; the fact tree is Ada's, passed through as Ada gave it."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.panel import CLOSENESS_URI
from glyphh_server.mcp.tools.base import Context, Done, Tool


class Near(BaseModel):
    model_config = ConfigDict(extra="ignore")
    closeness: float = Field(ge=0, le=1)
    like: str = Field(max_length=200, description="A fake's made-up name and role; a real one's source and category")


class Side(BaseModel):
    model_config = ConfigDict(extra="ignore")
    closeness: float | None = Field(None, ge=0, le=1, description="The nearest one's; none when none is held")
    nearest: list[Near] = Field(default_factory=list, max_length=10)


class Part(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fake: Side
    real: Side
    reads: str = Field(max_length=120, description="reads like the fakes, reads like real people, between the two")


class Decision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    outcome: str | None = Field(None, max_length=40)
    confidence: float | None = Field(None, ge=0, le=1)
    ask: bool = False
    on: str = Field("resume", max_length=20, description="What Ada decided on: the resume, or the letter")
    facts: list[dict[str, Any]] | None = Field(None, max_length=10, description="Ada's fact trees, as Ada gave them")


class Closeness(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resume: Part | None = None
    letter: Part | None = None
    decision: Decision | None = None
    reads: str | None = Field(None, max_length=120, description="Said when there was nothing to read")
    note: str | None = Field(None, max_length=300)


def _said(name: str, part: Part) -> str:
    sides = ", ".join(
        f"closest {side} {'none held' if got.closeness is None else f'{got.closeness:.2f}'}"
        for side, got in (("fake", part.fake), ("real", part.real))
    )
    return f"The {name}: {sides}: {part.reads}."


async def closeness(ctx: Context, args: Closeness) -> Done:
    lines = [_said(name, part) for name, part in (("resume", args.resume), ("cover letter", args.letter)) if part]
    if args.decision and args.decision.outcome:
        sure = "" if args.decision.confidence is None else f" ({args.decision.confidence:.0%})"
        asks = "; Ada would ask a person first" if args.decision.ask else ""
        lines.append(f"Ada decides {args.decision.outcome}{sure}{asks}.")
    return Done(
        " ".join(lines) or args.reads or "There was nothing to read.", args.model_dump(mode="json", exclude_none=True)
    )


TOOLS: tuple[Tool, ...] = (
    Tool(
        "screener_closeness",
        "Show how close a resume is to real people or fakes",
        "Show the Resume Screener's simple check as a card: how close a resume and a cover letter are to real "
        "people's and to fakes, the nearest few on each side, and Ada's decision with its confidence and its fact "
        "tree. Give it exactly what the Resume Screener plugin's check.py printed. It decides and keeps nothing.",
        Closeness,
        closeness,
        True,
        True,
        CLOSENESS_URI,
    ),
)
