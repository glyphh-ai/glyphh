"""The Resume Screener's verdict card (mcp/panel.py, `ui://glyphh/screener/1`). The Resume Screener is a plugin
(github.com/glyphh-ai/plugins, plugins/resume-screener): its skill reads an application with its own code, asks the
person's Ada models through ada_facts and ada_decide, and works out the verdict. A plugin cannot show a panel, so
it hands the verdict to `screener_verdict`, which answers it unchanged for the card to draw: is this a real person
(each signal, what it found and who said so), the fit second, how it was written as one line. The tool decides
nothing, reads nothing and keeps nothing. A signal the person is asked about may carry `teach`: the tool and
arguments that record their answer (ada_record, the signal's model and the case), which the card calls."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.panel import SCREENER_URI
from glyphh_server.mcp.tools.base import Context, Done, Tool

Says = Literal["fine", "suspect", "unsure", "not checked"]


class Teach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["ada_record"] = Field(description="The tool that records the person's answer")
    args: dict[str, Any] = Field(description="Its arguments without the outcome: the model's name and the case")


class Signal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    signal: str = Field(max_length=40, description="timing, files, others or greenhouse")
    title: str = Field(max_length=80)
    says: Says
    by: Literal["ada", "rule", "you"] = Field(description="Who said it: Ada, the rule when Ada was unsure, the person")
    confidence: float | None = Field(None, ge=0, le=1)
    found: list[str] = Field(default_factory=list, max_length=12, description="What the check found, in sentences")
    teach: Teach | None = None


class Person(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verdict: Literal["real person", "suspect", "unsure"]
    signals: list[Signal] = Field(max_length=8)
    ask: list[str] = Field(default_factory=list, max_length=8, description="The signals the person is asked about")


class Decided(BaseModel):
    model_config = ConfigDict(extra="ignore")
    outcome: str = Field(max_length=40)
    confidence: float | None = Field(None, ge=0, le=1)
    ask: bool = False
    found: list[str] = Field(default_factory=list, max_length=12)


class Verdict(BaseModel):
    model_config = ConfigDict(extra="ignore")
    applicant: str = Field(max_length=200, description="The applicant and the role, as the screener labels them")
    role: str = Field("", max_length=200)
    person: Person = Field(description="Is this a real person: the verdict and each signal")
    fit: Decided = Field(description="How well they fit the role: strong, borderline or poor")
    made: Decided = Field(description="How much of the text reads as generated: some, mostly or fully")


async def verdict(ctx: Context, args: Verdict) -> Done:
    shown = args.model_dump(mode="json", exclude_none=True)
    fit = f"{args.fit.outcome} fit" if not args.fit.ask else f"fit unsure ({args.fit.outcome})"
    signals = "; ".join(f"{s.title}: {s.says}" for s in args.person.signals)
    return Done(f"{args.applicant}: {args.person.verdict} ({signals}). {fit[:1].upper()}{fit[1:]}.", shown)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "screener_verdict",
        "Show a screening verdict",
        "Show the Resume Screener's verdict for one application as a card: real person, suspect or unsure with what "
        "each signal found, then the fit, then how it was written. Give it the verdict exactly as the Resume Screener "
        "plugin's verdict step printed it. It decides and keeps nothing.",
        Verdict,
        verdict,
        True,
        True,
        SCREENER_URI,
    ),
)
