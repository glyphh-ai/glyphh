"""The Resume Screener's file checks: what an application's files themselves say, apart from
what their words mean. `of` reads one file (filefacts_pdf.py, filefacts_docx.py) and its text's own marks:
characters that are there but never seen (zero-width, direction marks, soft hyphens) and what pasting from a chat
leaves behind (markdown marks, a placeholder never filled in, the chat's own words). `whole` makes the two files'
facts the application's `file`, as the file model reads it; `flags` names what in it a person would want to know,
and `found` says each in a sentence. It measures and names; whether a flag matters is the person's to teach."""

import re
from datetime import datetime
from typing import Any

from . import filefacts_docx, filefacts_pdf

UNSEEN: re.Pattern[str] = re.compile("[​-‏‪-‮⁠-⁤﻿­]")
PASTED: dict[str, re.Pattern[str]] = {
    "markdown": re.compile(r"\*\*[^*\n]+\*\*|^#{1,4} \w|^```", re.M),
    "placeholder": re.compile(r"\[(?:your|company|hiring manager|insert|name|date|position)[^\]\n]{0,40}\]", re.I),
    "chat": re.compile(r"\b(?:as an ai|here(?:'s| is) (?:a|an|the|your) (?:\w+ ){0,3}(?:resume|cover letter|draft)|"
                       r"i hope this helps|let me know if you(?:'d| would) like)\b", re.I),
}  # fmt: skip
AI_TOOLS: tuple[str, ...] = ("chatgpt", "openai", "claude", "anthropic", "gemini", "copilot")
NO_ONE: frozenset[str] = frozenset(
    ("anonymous", "unknown", "user", "admin", "author", "owner", "python", "docx", "office", "microsoft", "windows")
)  # an author's name that names no person: what programs write when no one is signed in
VERSION: re.Pattern[str] = re.compile(r"[\d.]+|\(.*?\)")
NONE: dict[str, Any] = {"kind": "none", "producer": "", "creator": "", "author": "", "created": "", "modified": "",
                        "saves": 1, "fonts": [], "tracked": 0, "hidden": 0, "white": 0, "tiny": 0, "unseen": 0,
                        "pasted": []}  # fmt: skip
SAID: dict[str, str] = {
    "hidden_text": "text a reader cannot see is in the file (marked hidden or drawn invisibly)",
    "white_text": "white text is in the file",
    "tiny_text": "text too small to read is in the file",
    "unseen_characters": "characters that are never seen (zero-width or direction marks) are in the words",
    "tracked_changes": "tracked changes were left in the document",
    "pasted": "marks of pasting from a chat are in the words",
    "other_author": "the file's author is not the applicant",
    "ai_tool": "the file says an AI tool made it",
}


def marks(text: str) -> dict[str, Any]:
    return {"unseen": len(UNSEEN.findall(text)), "pasted": sorted(n for n, p in PASTED.items() if p.search(text))}


def of(kind: str, data: bytes, text: str) -> dict[str, Any]:
    """One file's facts; a file that cannot be walked keeps only its text's marks."""
    try:
        read = filefacts_pdf.facts(data) if kind == "pdf" else filefacts_docx.facts(data) if kind == "docx" else {}
    except Exception:  # noqa: BLE001  any parser's failure on a bad file: nothing is known of the file
        read = {}
    return NONE | read | marks(text) | {"kind": kind}


def tool(said: str) -> str:
    """A program's name without its version: `Microsoft Word 16.0` and `microsoft word` are one."""
    return " ".join(VERSION.sub(" ", said.lower()).split()[:4]) or "none"


def _gap(created: str, modified: str) -> str:
    """How long after it was made the file was last changed: never, minutes, hours, days, or unknown."""
    try:
        seconds = (datetime.fromisoformat(modified) - datetime.fromisoformat(created)).total_seconds()
    except ValueError:
        return "unknown"
    return "never" if seconds < 60 else "minutes" if seconds < 3600 else "hours" if seconds < 86400 else "days"


def _author(author: str, name: str) -> str:
    """Whose the file says it is: the applicant's, another's, or no one's (unsaid, or a program's stand-in name)."""
    said = set(re.findall(r"[a-z]+", author.lower()))
    if not said - NO_ONE:
        return "none"
    return "applicant" if said & {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 1} else "other"


def whole(resume: dict[str, Any], letter: dict[str, Any], name: str) -> dict[str, Any]:
    """The application's `file`: the resume's file facts, and what its two files hold between them (`tools_said`,
    the programs' names as the files give them, is for `flags` alone)."""
    both = [f for f in (resume, letter) if f["kind"] != "none"]
    count = {k: min(999, sum(f[k] for f in both)) for k in ("hidden", "white", "tiny", "unseen", "tracked")}
    made = {
        "kind": resume["kind"], "tool": tool(resume["producer"]), "made_with": tool(resume["creator"]),
        "author": _author(resume["author"], name), "edited": _gap(resume["created"], resume["modified"]),
        "saves": min(50, resume["saves"]), "fonts": len(resume["fonts"]),
        "same_tool": "one" if len(both) < 2 else "yes" if len({tool(f["producer"]) for f in both}) == 1 else "no",
        "pasted": sorted({p for f in both for p in f["pasted"]}) or ["none"], **count,
    }  # fmt: skip
    return made | {"tools_said": " ".join(f"{f['producer']} {f['creator']}" for f in both).lower()[:300]}


def flags(file: dict[str, Any], tools: str = "") -> list[str]:
    found = [
        ("hidden_text", file["hidden"] > 0), ("white_text", file["white"] > 0), ("tiny_text", file["tiny"] > 0),
        ("unseen_characters", file["unseen"] > 0), ("tracked_changes", file["tracked"] > 0),
        ("pasted", file["pasted"] != ["none"]), ("other_author", file["author"] == "other"),
        ("ai_tool", any(t in tools.lower() for t in AI_TOOLS)),
    ]  # fmt: skip
    return [name for name, there in found if there] or ["none"]


def found(file: dict[str, Any]) -> list[str]:
    """What the file checks found, each in a sentence (none: nothing a person would want to know)."""
    return [SAID[f] for f in file["flags"] if f in SAID]
