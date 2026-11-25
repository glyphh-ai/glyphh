"""An application against the others seen (the Resume Screener's `others` step; docs/checks.md). Every application is kept in one Ada model, `others`, as what it holds apart from who sent
it: its work history (employers, titles, each job's dates, the education line), its phrasing (the summary, the
duties, the cover letter) and its contact details (phones, email addresses, the name part of each address, links).
A new application is asked of that model three ways, one part at a time, and Ada answers the nearest it holds for
each with how alike they are (its own similarity, on its nearest precedents). What comes back at or above the
part's ceiling is named: the same history under another name, the same phrasing under another name, a contact
detail shared with another name, the same name applying again, a burst of near-identical applications. It measures
and names; whether it makes an applicant suspect is the verdict's and the person's to say."""

import json
import re
from collections.abc import Callable
from typing import Any

from . import resumes, sections

Case = dict[str, Any]
Ask = Callable[[Case], list[dict[str, Any]]]  # a part of a case: the nearest held (`nearest`), nearest first
PARTS: tuple[str, ...] = ("history", "words", "contact", "when")
CEILING: dict[str, float] = {"history": 0.9, "words": 0.47, "contact": 0.3, "when": 0.15}  # chosen on the design runs
BURST: int = 3  # this many held applications as near as the ceiling make a burst
TOP: int = 8
PHONE: re.Pattern[str] = re.compile(r"(?<![\d-])(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")  # not a span of years
LINK: re.Pattern[str] = re.compile(r"(?:https?://|www\.)[^\s)>\],]+", re.I)
# An address whole, an apostrophe in its name part too: read without it, every O'Brien's address is the same one.
EMAIL: re.Pattern[str] = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
SAID: dict[str, str] = {
    "same_history": "the same work history as {who}, under another name",
    "same_words": "the same phrasing as {who}, under another name",
    "shared_contact": "a contact detail shared with {who}, another name",
    "applied_before": "the same person as {who}, applying again",
    "burst": "{n} near-identical applications are already held",
}


def _name(said: str) -> str:
    return " ".join(re.findall(r"[a-z]+", said.lower()))


def contacts(said: str) -> dict[str, list[str]]:
    """The phones (their last ten digits), email addresses, each address's name part without its digits, and links."""
    digits = {re.sub(r"\D", "", p)[-10:] for p in PHONE.findall(said)}
    emails = {e.lower() for e in EMAIL.findall(said)}
    handles = {re.sub(r"[^a-z]", "", e.split("@")[0]) for e in emails}
    links = {m.lower().rstrip("/.") for m in LINK.findall(said)}
    found = {"phones": digits, "emails": emails, "handles": handles, "links": links}
    return {k: sorted(v for v in vs if len(v) > 3) for k, vs in found.items()}


def prints(app: dict[str, Any]) -> Case:
    """The application as the `others` model holds it. A part with nothing in it is left out, so two applications
    are never alike for both having no phone."""
    text = app.get("text") or {}
    resume, letter, email = (str(text.get(k) or "") for k in ("resume", "letter", "email"))
    parts = sections.split(resume)
    jobs = sections.entries(parts["experience"] or resume)
    duties = " ".join(ln for ln in parts["experience"].splitlines() if not resumes.SPAN.search(ln))
    held: dict[str, dict[str, Any]] = {
        "history": {"employers": [j["employer"].lower() for j in jobs if j["employer"]],
                    "titles": [j["title"].lower() for j in jobs if j["title"]],
                    "spans": [j["span"] for j in jobs], "school": " ".join(parts["education"].split())[:300]},
        "words": {"summary": " ".join(parts["summary"].split())[:800], "duties": " ".join(duties.split())[:2000],
                  "letter": " ".join(letter.split())[:2000]},
        "contact": contacts(f"{email}\n{letter}\n{resume}"),
        "when": {"windows": list((app.get("timing") or {}).get("windows") or [])},  # the ten minutes it arrived in
    }  # fmt: skip
    who = {"name": _name(str(app.get("name") or "")), "label": str(app.get("label") or ""), "id": str(app.get("id"))}
    tag = json.dumps([who["name"], who["label"], who["id"]])  # who it is, carried in each part and weighing nothing
    case = {part: {"s": kept | {f"{part}_who": tag}} for part, roles in held.items()
            if (kept := {k: v for k, v in roles.items() if v})}  # fmt: skip
    return case | {"who": {"s": who}}


def _tagged(tree: Any) -> list[str]:
    """Who a fact tree is of: the `<part>_who` its record carries (name, label, id)."""
    if not isinstance(tree, dict):
        return ["", "", ""]
    if str(tree.get("key", "")).endswith("_who") and tree.get("record"):
        said = tree["record"][0] if isinstance(tree["record"], list) else tree["record"]
        return [str(x) for x in json.loads(said)]
    found = (_tagged(child) for child in tree.get("children") or [])
    return next((f for f in found if f[2]), ["", "", ""])


def nearest(facts: Any) -> list[dict[str, Any]]:
    """Ada's nearest fact trees as {sim, name, label, id}, nearest first."""
    out = []
    for f in facts or []:
        name, label, mid = _tagged(f.get("tree"))
        out.append({"sim": float(f.get("score") or 0.0), "name": name, "label": label, "id": mid})
    return out


def compared(ask: Ask, case: Case) -> dict[str, Any]:
    """What the model holds nearest to the case, part by part, and the flags: {near: {part: {sim, who, id}},
    flags, found, together}. Its own earlier record (the same id) is never its neighbour. `together` is how many
    held applications arrived within ten minutes of it: no flag here, the timing check names it (timing.py)."""
    me = case["who"]["s"]
    near: dict[str, Any] = {}
    flags: list[str] = []
    crowd = together = 0
    for part in PARTS:
        if part not in case:
            continue
        others = [n for n in ask({part: case[part]}) if n["id"] != me["id"]]
        close = [n for n in others if n["sim"] >= CEILING[part]]
        if others:
            near[part] = {"sim": round(others[0]["sim"], 4), "who": others[0]["label"], "id": others[0]["id"]}
        if part == "when":
            together = len(close)
            continue
        if close:
            same = close[0]["name"] == me["name"]
            flags.append("applied_before" if same else {"contact": "shared_contact"}.get(part, f"same_{part}"))
        crowd = max(crowd, len(close) if part != "contact" else 0)
    flags = list(dict.fromkeys(flags)) + (["burst"] if crowd >= BURST else [])
    first = next(iter(near.values()), {"who": ""})
    said = [SAID[f].format(who=near.get(_part(f), first)["who"], n=crowd) for f in flags]
    return {"near": near, "flags": flags or ["none"], "found": said or ["nothing like it is held"],
            "together": together}  # fmt: skip


def _part(flag: str) -> str:
    return {"same_history": "history", "same_words": "words", "shared_contact": "contact"}.get(flag, "history")
