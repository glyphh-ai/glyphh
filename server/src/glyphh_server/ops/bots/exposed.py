"""The tools a bot adds to the org's Glyphh connector, by purpose (docs/specs/bots.md, 9, Tools by purpose): a resume
screener's screen_application, applicants and correct, say, beside the generic bot_run. A bot template declares them
(library/<slug>/glyphh.json, `connector_tools`) and an installed bot keeps its copy; any bot may declare its own.
Each is one of the bot's ops: `run` (a run of the bot with the tool's arguments as its message, waited on up to
`wait` seconds, answered with what its `verdicts` decision decided), `runs` (its recent runs, each so), `wrong` (a
verdict of the decision its `gate` names corrected, learned in Ada) or `answer` (a run that waits on the person,
answered).
mcp/tools/bot_tools.py lists and calls them."""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.errors import Invalid

ABOUT: str = (
    "The tools it adds to the org's connector by purpose, each a name, a description and one of its ops: run (on "
    "the tool's text arguments), runs, wrong (corrects one of its decisions) or answer"
)
NAME: str = r"^[a-z][a-z0-9_]{0,47}$"
MINE: str = "glyphh_"  # a template's tools' (mcp/tools/templates.py)
ARG: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class ConnectorTool(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=NAME, description="Its name in the connector: screen_application")
    title: str = Field("", max_length=80, description="Its title; left out, its name")
    description: str = Field(min_length=1, max_length=1000, description="What it does, for Claude to find it by")
    op: Literal["run", "runs", "wrong", "answer"] = Field(description="Which of the bot's ops it is")
    args: dict[str, str] = Field(
        default_factory=dict, max_length=20, description="op run: its arguments, each name: what it is (text)"
    )
    required: list[str] = Field(default_factory=list, max_length=20, description="op run: the arguments it needs")
    given: str | None = Field(None, description="op run: the argument whose text is the run's message; else all, JSON")
    verdicts: str | None = Field(None, description="op run, runs: the decision whose verdicts are answered")
    gate: str | None = Field(None, description="op wrong: the decision it corrects")
    wait: int = Field(0, ge=0, le=50, description="op run: seconds to wait for the run to end (0: answered queued)")


def _problems(spec: dict[str, Any], tool: ConnectorTool) -> list[str]:
    decisions = spec.get("gates") or {}
    said = [f"its name may not begin {MINE}"] if tool.name.startswith(MINE) else []
    said += [f"argument {a} is not a lowercase name" for a in tool.args if not ARG.match(a)]
    said += [f"required {r} is not one of its args" for r in tool.required if r not in tool.args]
    if tool.args and tool.op != "run":
        said.append("only a run takes args (the other ops' arguments are fixed)")
    if tool.given is not None and tool.given not in tool.args:
        said.append(f"given {tool.given} is not one of its args")
    if tool.verdicts is not None and tool.verdicts not in decisions:
        said.append(f"verdicts {tool.verdicts} is not one of the bot's decisions")
    if tool.op == "wrong" and (tool.gate is None or tool.gate not in decisions):
        said.append("a wrong corrects one of the bot's decisions: name it as gate")
    return [f"{tool.name}: {s}" for s in said]


def check(spec: dict[str, Any], given: list[dict[str, Any]]) -> None:
    """Each tool fits the bot's decisions, and no two share a name; every problem said at once (Invalid)."""
    tools = [ConnectorTool.model_validate(t) for t in given]
    names = [t.name for t in tools]
    problems = [f"{n}: two tools have this name" for n in sorted({n for n in names if names.count(n) > 1})]
    for tool in tools:
        problems += _problems(spec, tool)
    if problems:
        raise Invalid("The bot's connector tools do not fit it.", reason="connector_tools", problems=problems)
