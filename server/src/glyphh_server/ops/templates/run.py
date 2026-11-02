"""A template's tool called (docs/specs/templates.md): its op's arguments, the op run over the person's models
(ops/templates/glyphh.py), and a short text with the same as data; and the context a hook puts before an AI, the
installed templates' `context` pulls as one block of text."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates import glyphh
from glyphh_server.ops.templates.library import Body, Op, ToolPart

KIND = Field(description="Which of the template's models: its kinds are in the tool's description")
TOP = Field(glyphh.TOP, ge=1, le=50, description="At most this many")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Remember(Strict):
    kind: str = KIND
    text: str = Field(min_length=1, max_length=glyphh.TEXT_MAX, description="What to keep, in a sentence")
    when: str | None = Field(None, max_length=500, description="The situation it applies to, in words")


class Recall(Strict):
    about: str = Field(min_length=1, max_length=glyphh.TEXT_MAX, description="What is at hand, in words")
    kind: str | None = Field(None, description="Only this kind; left out, every kind the tool covers")
    top: int = TOP


class Listing(Strict):
    about: str | None = Field(None, max_length=glyphh.TEXT_MAX, description="Only what applies to this, in words")
    top: int = TOP


class Forget(Strict):
    kind: str = KIND
    id: str = Field(min_length=1, max_length=200, description="Its id, as recall or a list answered it")


ARGS: dict[Op, type[Strict]] = {"remember": Remember, "recall": Recall, "list": Listing, "forget": Forget}


def lines(found: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {f['text']} ({f['kind']} {f['id']})" for f in found)


async def _read(state: Any, who: Principal, body: Body, kinds: list[str], about: str | None, top: int) -> list[Any]:
    found: list[dict[str, Any]] = []
    for kind in kinds:
        if about:
            found += await glyphh.recall(state, who, body, kind, about, top)
        else:
            found += await glyphh.newest(state, who, body, kind, top)
    return sorted(found, key=lambda f: -f["score"])[:top] if about else found


async def run(state: Any, who: Principal, body: Body, tool: ToolPart, args: Any) -> tuple[str, dict[str, Any]]:
    kinds = body.kinds(tool)
    if tool.op == "remember":
        made = await glyphh.remember(state, who, body, glyphh.kind_of(body, kinds, args.kind), args.text, args.when)
        return f"Kept in your glyphh ({made['kind']} {made['id']}): {args.text}", made
    if tool.op == "forget":
        gone = await glyphh.forget(state, who, body, glyphh.kind_of(body, kinds, args.kind), args.id)
        return f"Forgot {args.kind} {args.id}.", gone
    if tool.op == "recall" and args.kind is not None:
        kinds = [glyphh.kind_of(body, kinds, args.kind)]
    found = await _read(state, who, body, kinds, args.about, args.top)
    return lines(found) or "Nothing in your glyphh bears on that yet.", {"found": found}


async def context(state: Any, who: Principal, bodies: list[Body], prompt: str | None) -> str:
    """What a hook puts before an AI: at a session's start each template's session pulls (a kind's newest), with a
    prompt its prompt pulls (a kind's closest to it), each under the model's title."""
    parts: list[str] = []
    for body in bodies:
        titles = {m.key: m.title for m in body.models}
        for pull in body.context.prompt if prompt else body.context.session:
            found = await _read(state, who, body, [pull.kind], prompt, pull.top)
            if found:
                parts.append(f"{titles[pull.kind]}:\n{lines(found)}")
    if not parts:
        return ""
    return "From your glyphh, your memory across every AI you use:\n\n" + "\n\n".join(parts)
