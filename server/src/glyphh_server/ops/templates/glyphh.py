"""A person's glyphh: the Ada models their installed templates made, and the four ops a template's tools are made of
(remember, recall, list, forget) over them, each one call to the Ada workers as the person (ops/templates/ada.py).
Each thing kept is a precedent whose outcome is the thing itself and whose situation is its words (cue: the
situation it applies to, then the text) and its kind; remembering the same text again replaces it (its key part).
recall reads the closest by words alone, list the newest of a kind."""

import hashlib
import uuid
from typing import Any

from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.templates.ada import ask
from glyphh_server.ops.templates.library import Body

TEXT_MAX: int = 2000
TOP: int = 10
RECALLED_LEAST: float = 0.05  # a recall's closest under this share no words with what was asked: left out


def model_name(user_id: uuid.UUID, slug: str, kind: str) -> str:
    """The person's model of one kind: `me-` and their id's first 12 hex digits, so a name says whose it is."""
    return f"me-{user_id.hex[:12]}-{slug}-{kind}"


def mine(user_id: uuid.UUID, model: str) -> bool:
    """Whether a model is this person's (a glyphh model of anyone else's is not theirs to read)."""
    return not model.startswith("me-") or model.startswith(f"me-{user_id.hex[:12]}-")


def _data(**roles: str) -> dict[str, Any]:
    return {"m": {"s": roles}}


def kind_of(body: Body, kinds: list[str], kind: str) -> str:
    if kind not in kinds:
        raise Invalid(f"{body.name} keeps {', '.join(kinds)}; not {kind!r}.", reason="kind", kinds=kinds)
    return kind


async def remember(state: Any, who: Principal, body: Body, kind: str, text: str, when: str | None) -> dict[str, Any]:
    key = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:16]
    data = _data(cue=f"{when or ''} {text}".strip(), kind=kind, key=key)
    made = await ask(state, who, model_name(who.user_id, body.slug, kind), "record", {"data": data, "outcome": text})
    return {"kind": kind, "id": made["id"], "text": text, "holds": made["precedents"]}


def _kept(kind: str, trees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"kind": kind, "id": t["id"], "text": t["outcome"], "score": t["score"]} for t in trees]


async def recall(state: Any, who: Principal, body: Body, kind: str, about: str, top: int) -> list[dict[str, Any]]:
    """The closest of a kind to `about`, by its words alone."""
    args = {"data": _data(cue=about), "top": top, "min_score": RECALLED_LEAST}
    return _kept(kind, await ask(state, who, model_name(who.user_id, body.slug, kind), "facts", args))


async def newest(state: Any, who: Principal, body: Body, kind: str, top: int) -> list[dict[str, Any]]:
    """A kind's newest: every one alike by kind, so ranked newest first."""
    args = {"data": _data(kind=kind), "top": top}
    return _kept(kind, await ask(state, who, model_name(who.user_id, body.slug, kind), "facts", args))


async def forget(state: Any, who: Principal, body: Body, kind: str, rid: str) -> dict[str, Any]:
    await ask(state, who, model_name(who.user_id, body.slug, kind), "forget", {"id": rid})
    return {"kind": kind, "id": rid, "forgotten": True}
