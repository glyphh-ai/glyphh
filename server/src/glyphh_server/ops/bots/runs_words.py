"""Small words shared by what a run says (ops/bots/said.py) and its record (ops/bots/runs.py)."""

import re

INTERRUPTED: str = "interrupted by a restart"
ENGINE_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgates\b", re.I), "decisions"),
    (re.compile(r"\bgate\b", re.I), "decision"),
    (re.compile(r"\bloop\b", re.I), "steps"),
)


def plain(text: str) -> str:
    """A reason of the runner's without its own words for things: a gate is a decision, the loop the steps."""
    for word, said in ENGINE_WORDS:
        text = word.sub(said, text)
    return text


def sentence(text: str) -> str:
    """Text as one sentence: its first letter a capital, a full stop at its end."""
    t = text.strip().rstrip(":;,")
    if not t:
        return ""
    return t[0].upper() + t[1:] + ("" if t[-1] in ".!?" else ".")


def named(step_id: str) -> str:
    """A step's or an outcome's id as words: `hot_leads` is "hot leads"."""
    return step_id.replace("_", " ").replace("-", " ").strip()


def joined(names: list[str]) -> str:
    """Names in a sentence: "a", "a and b", "a, b and c"."""
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
