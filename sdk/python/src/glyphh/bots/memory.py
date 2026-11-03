"""Memory, kept in Ada: each bot (and the orchestrator) has three models of its own (memory, instructions,
personality), every line a precedent whose outcome is the line itself, found again by what it is about. The person's
own glyphh (Agentic memory: me-<id>-agentic-memory-<kind>) is read too, when they have one."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from ..client import Ada
from .package import KINDS, Bot

#: The spec every memory model is made from.
MEMORY_SPEC: Dict[str, Any] = {
    "name": "bot-memory",
    "seed": 7,
    "dimension": 2048,
    "layers": [
        {
            "name": "m",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "cue", "text_encoding": "bag_of_words"},
                        {"name": "kind", "similarity_weight": 0.1},
                        {"name": "key", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
}
#: A recalled line under this score says nothing about the cue.
RECALL_FLOOR = 0.05
GLYPHH_MEMORY = re.compile(r"me-[0-9a-f]{12}-agentic-memory-(\w+)")


def memory_case(cue: str, kind: Optional[str] = None, text: Optional[str] = None) -> Dict[str, Any]:
    """The case a line is kept as (`text`: the line, keyed by its words so the same line is kept once) or looked up
    by (only the cue)."""
    s: Dict[str, Any] = {"cue": cue}
    if kind:
        s["kind"] = kind
    if text:
        s["key"] = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:16]
    return {"m": {"s": s}}


def remember(ada: Ada, model: str, kind: str, text: str, when: str = "") -> None:
    """Keep one line in a memory model."""
    ada.model(model).record(memory_case(f"{when} {text}".strip(), kind, text), text)


def recall(ada: Ada, model: str, about: str, top: int) -> List[str]:
    """The lines a memory model holds that bear on `about`, best first; [] when it holds none."""
    try:
        trees = ada.model(model).facts(memory_case(about), top=top).data
    except Exception:  # noqa: BLE001  an empty or missing model has nothing to say
        return []
    found = []
    for t in trees if isinstance(trees, list) else []:
        if isinstance(t, dict) and t.get("outcome") and float(t.get("score", 1)) >= RECALL_FLOOR:
            found.append(str(t["outcome"]))
    return found


def glyphh_models(ada: Ada) -> Dict[str, str]:
    """The person's own glyphh (Agentic memory), its model for each kind, when they have one."""
    found = {}
    for m in ada.models():
        hit = GLYPHH_MEMORY.fullmatch(m.name)
        if hit and hit.group(1) in KINDS:
            found[hit.group(1)] = m.name
    return found


def memory_context(ada: Ada, bot: Bot, about: str) -> str:
    """What is put before the bot's agent: the person's rules and personality (from their glyphh, unless the bot
    says `reads_glyphh: false`), then the bot's own rules and personality, then what it remembers of earlier runs."""
    parts = []
    if bot.reads_glyphh:
        mine = glyphh_models(ada)
        for kind, title in (("instructions", "The person's rules"), ("personality", "How the person likes it")):
            got = recall(ada, mine[kind], about, 10) if kind in mine else []
            if got:
                parts.append(f"{title}:\n" + "\n".join(f"- {g}" for g in got))
    for kind, title in (
        ("instructions", "Your rules"),
        ("personality", "Your personality"),
        ("memory", "What you remember from earlier runs"),
    ):
        got = recall(ada, bot.memory_model(kind), about, 8)
        if got:
            parts.append(f"{title}:\n" + "\n".join(f"- {g}" for g in got))
    return "\n\n".join(parts)
