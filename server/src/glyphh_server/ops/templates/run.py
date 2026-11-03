"""A template's tool called (docs/specs/templates.md): its op's arguments, the op run over the person's models
(ops/templates/glyphh.py, and bots.py for make, decide and record), and a short text with the same as data; and the
context a hook puts before an AI, the installed templates' `context` pulls as one block of text."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates import bots, glyphh
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


MODEL = Field(min_length=1, max_length=63, description="A model's key (in the tool's description) or a made one's name")
DATA = Field(description="The case in the model's spec's shape: {layer: {segment: {role: value}}}")


class Make(Strict):
    name: str = Field(pattern=bots.NAME, description="The new model's name, lower case: its full name starts me-")
    spec: dict[str, Any] = Field(description="Its Ada spec: layers, segments, roles and output, as ada_model_create's")


class Decide(Strict):
    model: str = MODEL
    data: dict[str, Any] = DATA


class Record(Decide):
    outcome: str = Field(min_length=1, max_length=200, description="What the outcome was, or should have been")


ARGS: dict[Op, type[Strict]] = {
    "remember": Remember,
    "recall": Recall,
    "list": Listing,
    "forget": Forget,
    "make": Make,
    "decide": Decide,
    "record": Record,
}


def decided(d: dict[str, Any]) -> str:
    p = d.get("probabilities", {}).get(d.get("outcome"), 0.0)
    ask = "ask the person first" if d.get("ask") else "no need to ask"
    return f"{d['model']}: {d.get('outcome')} ({100 * p:.0f}%); {ask}."


async def _bot(state: Any, who: Principal, body: Body, tool: ToolPart, args: Any) -> tuple[str, dict[str, Any]]:
    """make, decide and record: over this install's models alone (ops/templates/bots.py)."""
    if tool.op == "make":
        made = await bots.make(state, who, body, args.name, args.spec)
        return f"{'Made' if made['made'] else 'Kept, as it was there already:'} {made['model']}.", made
    if tool.op == "decide":
        d = await bots.decide(state, who, body, body.kinds(tool), args.model, args.data)
        return decided(d), d
    done = await bots.record(state, who, body, body.kinds(tool), args.model, args.data, args.outcome)
    return f"Recorded {args.outcome} in {done['model']} ({done['id']}, {done['precedents']} precedents).", done


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
    if tool.op in ("make", "decide", "record"):
        return await _bot(state, who, body, tool, args)
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
