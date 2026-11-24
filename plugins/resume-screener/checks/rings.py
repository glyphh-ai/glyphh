"""The made-up rings of check 1 (docs/checks.md): from a base application's text, the same application under a new
name and contact details; reworded; its sections reordered; one job changed; and a stranger given the base's phone
number. Made by code from generated applications: none of it is a real fraud ring."""

import hashlib
import re
from typing import Any

from screener import applicants, others, resumes, sections

FIRST: tuple[str, ...] = ("Avery", "Blake", "Casey", "Devon", "Ellis", "Finley", "Gray", "Harper", "Indra", "Jules",
                          "Kiran", "Lane", "Morgan", "Noor", "Oakley", "Perry", "Quinn", "Reese", "Sage", "Tatum")  # fmt: skip
LAST: tuple[str, ...] = ("Abara", "Brandt", "Calloway", "Desrosiers", "Eklund", "Fairbanks", "Galvez", "Hollis",
                         "Ibarra", "Jorgensen", "Kaczmarek", "Lindqvist", "Marchetti", "Nakagawa", "Oyelaran",
                         "Pemberton", "Quintero", "Rasmussen", "Sokolov", "Thackeray")  # fmt: skip
SWAPS: dict[str, str] = {
    "built": "developed", "led": "headed", "managed": "oversaw", "designed": "devised", "helped": "assisted",
    "improved": "bettered", "wrote": "authored", "worked": "served", "experience": "background", "team": "group",
    "strong": "solid", "ran": "operated", "set up": "established", "many": "numerous", "also": "additionally",
    "use": "employ", "like": "enjoy", "role": "position", "job": "post", "really": "truly",
}  # fmt: skip
VARIANTS: tuple[str, ...] = ("renamed", "reworded", "reordered", "one job changed", "burst", "shared contact")


def groups(train: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """The train rows split by a fixed hash of their id, as the protocol says."""
    order = sorted(train, key=lambda r: hashlib.sha256(f"glyphh-others-1:{r['id']}".encode()).hexdigest())
    cuts = {"held bases": 150, "held controls": 150, "design bases": 100, "design controls": 100}
    out, at = {}, 0
    for name, n in cuts.items():
        out[name], at = order[at : at + n], at + n
    return out | {"population": order[at:]}


def parts_of(row: dict[str, Any]) -> dict[str, str]:
    """The row's text as its parts: the role (its subject), the email, the cover letter and the resume."""
    head, _, resume = row["text"].partition("\n\nRESUME\n")
    mail, _, letter = head.partition("\n\nCOVER LETTER\n")
    subject, _, body = mail.partition("\n")
    return {"role": subject.removeprefix("Subject:").strip(), "email": body.strip(), "letter": letter, "resume": resume}


def renamed(parts: dict[str, str], n: int) -> dict[str, str]:
    """The same application under the nth new name, with a new email address and a new phone number."""
    was = resumes.fields(parts["resume"], "", "")["name"].split()
    first, last = FIRST[n % len(FIRST)], LAST[(n // len(FIRST) + n) % len(LAST)]
    email, phone = f"{first}.{last}{n}@postbox.example".lower(), f"(555) 01{n % 10}-{1000 + n:04d}"
    out = {}
    for key, said in parts.items():
        said = others.EMAIL.sub(email, others.PHONE.sub(phone, said))
        for old, new in zip((was[:1] + was[-1:]) if len(was) > 1 else [], (first, last), strict=False):
            said = re.sub(rf"\b{re.escape(old)}\b", new, said)
        out[key] = said
    return out


def reworded(parts: dict[str, str]) -> dict[str, str]:
    def swap(said: str) -> str:
        for old, new in SWAPS.items():
            said = re.sub(rf"\b{old}\b", new, said, flags=re.I)
        return said

    lines = [ln if resumes.SPAN.search(ln) else swap(ln) for ln in parts["resume"].splitlines()]
    return parts | {"resume": "\n".join(lines), "letter": swap(parts["letter"]), "email": swap(parts["email"])}


def reordered(parts: dict[str, str]) -> dict[str, str]:
    cut = sections.split(parts["resume"])
    again = [cut["head"], *(f"{name.upper()}\n{cut[name]}" for name in ("skills", "education", "experience", "summary"))]
    return parts | {"resume": "\n".join(again)}


def _first_job(resume: str) -> tuple[int, int, list[str]]:
    """Where the resume's first job stands (its lines' first and last index), and the resume's lines."""
    lines = resume.splitlines()
    starts = [i for i, ln in enumerate(lines) if resumes.SPAN.search(ln)]
    ends = [i for i, ln in enumerate(lines) if sections.HEADING.match(ln) and starts and i > starts[0]]
    stop = min([*starts[1:2], *ends[:1], len(lines)])
    return (starts[0], stop, lines) if starts else (0, 0, lines)


def one_job_changed(parts: dict[str, str], donor: dict[str, str]) -> dict[str, str]:
    a, b, lines = _first_job(parts["resume"])
    c, d, theirs = _first_job(donor["resume"])
    return parts | {"resume": "\n".join([*lines[:a], *theirs[c:d], *lines[b:]])}


def shared_contact(control: dict[str, str], base: dict[str, str]) -> dict[str, str]:
    """The control (another person, another history) carrying the base's phone number in place of its own; a
    control that gives no phone has it added under its name."""
    phone = others.PHONE.search(base["resume"] + base["letter"] + base["email"])
    theirs = phone.group(0) if phone else "(555) 000-0000"
    out = {k: others.PHONE.sub(theirs, v) for k, v in control.items()}
    if theirs not in out["resume"]:
        first, _, rest = out["resume"].partition("\n")
        out["resume"] = f"{first}\n{theirs}\n{rest}"
    return out


def case_of(mid: str, parts: dict[str, str]) -> dict[str, Any]:
    """The text as the `others` model holds an application (no email headers: no arrival time)."""
    raw, _ = applicants.of_given(mid, dict(parts), raw=True)
    assert raw is not None
    return others.prints(raw)
