"""Two of a bot's settings its owner chooses (docs/specs/bots.md, 13): the folders of its rrotor's machine it may read
or change, and how hard Claude works on its agent steps.

Folders are `[{path, access: "read" | "write"}]`, used only when the bot runs on a rrotor (Glyphh cloud has no
folders: they are kept and ignored there). The server knows nothing of the machine's files, so it checks the shape
alone: an absolute path with no `..`, at most MAX of them, none twice. Whether a path is one the machine's owner
offers is the rrotor's to say, at each run (rrotor's docs/architecture.md, 5.11); it mounts exactly these in the run's
sandbox. Every rrotor that runs a bot's agent (0.9.0, ops/bots/remote.py) takes both.

Effort is the Claude API's own `output_config.effort`: `low`, `medium`, `high`, `xhigh` or `max`, `medium` unless the
owner says. It goes with the bot's turn when its model takes it (the three bot models take all five) and is left out
otherwise: a run never fails over it."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.errors import Invalid

MAX: int = 20
PATH_MAX: int = 1024

Effort = Literal["low", "medium", "high", "xhigh", "max"]
EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT: str = "medium"
# the Claude models that take output_config.effort, and the levels each takes (docs/specs/bots.md, 13)
EFFORT_MODELS: dict[str, tuple[str, ...]] = {
    "claude-opus-5-5": EFFORTS,
    "claude-sonnet-5-5": EFFORTS,
    "claude-haiku-5-5": EFFORTS,
}
FOLDERS_ABOUT: str = (
    "The folders of its rrotor's machine it may use, each {path (absolute), access: read or write}; at most 20; "
    "used only when it runs on a rrotor, which gives it exactly these and refuses one its owner does not offer"
)
EFFORT_ABOUT: str = "How hard Claude works on its agent steps: low, medium (the default), high, xhigh or max"


class Folder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=PATH_MAX, description="The folder's absolute path on the machine")
    access: Literal["read", "write"] = Field(description="read: read only; write: read and change")


class Chosen(BaseModel):
    """The two settings as a bot shows them (ops/bots/views.py's BotView)."""

    folders: list[Folder] = Field(description=FOLDERS_ABOUT)
    effort: Effort = Field(description=EFFORT_ABOUT)


class ChosenIn(BaseModel):
    """As a bot is made with them: no folders and medium effort unless said."""

    folders: list[Folder] = Field(default_factory=list, max_length=100, description=FOLDERS_ABOUT)
    effort: Effort = Field("medium", description=EFFORT_ABOUT)


class ChosenPatch(BaseModel):
    """As a bot is changed: either left as it is when not given."""

    folders: list[Folder] | None = Field(None, max_length=100, description=FOLDERS_ABOUT + " (the whole list)")
    effort: Effort | None = Field(None, description=EFFORT_ABOUT)


def folders(given: list[Folder]) -> list[dict[str, str]]:
    """The folders as they are kept, or Invalid saying in a plain sentence what is wrong with them."""
    if len(given) > MAX:
        raise Invalid(f"A bot may be given at most {MAX} folders: this is {len(given)}.", reason="folders")
    kept: list[dict[str, str]] = []
    for one in given:
        path = one.path if one.path == "/" else one.path.rstrip("/")
        if not path.startswith("/") or "\x00" in path:
            raise Invalid(f"{one.path!r} is not an absolute path: a folder is named from /.", reason="folders")
        if ".." in path.split("/"):
            raise Invalid(f"{one.path} has '..' in it: name the folder itself.", reason="folders")
        if any(k["path"] == path for k in kept):
            raise Invalid(f"{path} is listed twice: give each folder once.", reason="folders")
        kept.append({"path": path, "access": one.access})
    return kept


def effort_for(model: str, effort: str | None) -> str | None:
    """The effort a request to this model carries; None when the model takes none, or not that level."""
    return effort if effort in EFFORT_MODELS.get(model, ()) else None


class WithEffort:
    """An `anthropic.Anthropic` as the SDK's ApiClaude calls it (`client.messages.stream(...)`), each request carrying
    the bot's effort as `output_config: {effort}` when its model takes it."""

    def __init__(self, client: Any, effort: str | None) -> None:
        self._client, self._effort = client, effort
        self.messages = self

    def stream(self, **kw: Any) -> Any:
        effort = effort_for(str(kw.get("model")), self._effort)
        if effort is not None and "output_config" not in kw:
            kw["output_config"] = {"effort": effort}
        return self._client.messages.stream(**kw)
