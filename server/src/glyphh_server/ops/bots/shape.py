"""What a bot gained when it became an agent you talk to (docs/specs/bot-agent-loop.md): its role (a bot, or the
org's one orchestrator), its standing task (what it does when it runs on its own), its example prompts (shown as
suggestions), its plugins (the know-how installed for it, each at the version installed) and where it can run (a
bot whose plugin carries code, or needs folders, runs only on a rrotor)."""

from typing import Literal

from pydantic import BaseModel, Field

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots.access import Chosen, ChosenIn, ChosenPatch

TASK_MAX: int = 4000
EXAMPLES_MAX: int = 6
EXAMPLE_MAX: int = 200
TASK_ABOUT: str = "Its standing task: what it does when it runs on its own (a scheduled run is given this)"
EXAMPLES_ABOUT: str = "Example prompts, shown as suggestions in its empty chat: at most 6, each at most 200 characters"
Place = Literal["cloud", "rrotor"]
PLACES: list[Place] = ["cloud", "rrotor"]


class PluginView(BaseModel):
    name: str
    version: str = Field(description="The version installed")
    latest: str = Field(description="The newest version Glyphh ships; the same when it is up to date")
    source: str = Field(description="template:<slug>, or personal (its own notes)")


class Shaped(Chosen):
    role: Literal["bot", "orchestrator"] = Field(description="orchestrator: the org's one; edited, never deleted")
    task: str = Field(description=TASK_ABOUT)
    examples: list[str] = Field(description=EXAMPLES_ABOUT)
    plugins: list[PluginView] = Field(description="The know-how installed for it")
    can_run_on: list[Place] = Field(description="Where it may run: cloud, rrotor, or only rrotor")


class ShapedIn(ChosenIn):
    task: str = Field("", max_length=TASK_MAX, description=TASK_ABOUT)
    examples: list[str] = Field(default_factory=list, max_length=EXAMPLES_MAX, description=EXAMPLES_ABOUT)


class ShapedPatch(ChosenPatch):
    task: str | None = Field(None, max_length=TASK_MAX, description=TASK_ABOUT)
    examples: list[str] | None = Field(None, max_length=EXAMPLES_MAX, description=EXAMPLES_ABOUT)


def examples(given: list[str]) -> list[str]:
    """The examples as they are kept: each trimmed, none empty, none too long (Invalid says which)."""
    kept = [e.strip() for e in given if e.strip()]
    long = [e for e in kept if len(e) > EXAMPLE_MAX]
    if long:
        raise Invalid(f"An example prompt is at most {EXAMPLE_MAX} characters: {long[0][:40]}… is longer.",
                      reason="examples")  # fmt: skip
    return kept


def limits(task: str, examples: list[str]) -> list[str]:
    """What a drafted bot's task and examples get wrong, each in a sentence: the limits a bot is made under."""
    out = [f"The standing task is at most {TASK_MAX:,} characters."] if len(task) > TASK_MAX else []
    if len(examples) > EXAMPLES_MAX:
        out.append(f"A bot has at most {EXAMPLES_MAX} example prompts: this has {len(examples)}.")
    if any(len(e.strip()) > EXAMPLE_MAX for e in examples):
        out.append(f"An example prompt is at most {EXAMPLE_MAX} characters.")
    return out
