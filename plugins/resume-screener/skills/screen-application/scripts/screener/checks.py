"""The Resume Screener's checks of an application once it is read (applicants.py), each a fixed step, in this
order:

- `content`: the resume split into its sections (sections.py), which the fit model reads.
- `filed`: what the files themselves say (filefacts.py) named as flags, which the files model reads.
- `timed`: what the email's timestamps say (timing.py), which the timing model reads.
- `written`: how each part was written (writing.py, signals.py), which the `made` model reads; the
  last step, so it drops the parts' whole text: what is handed on is short.

Each takes the application and answers it with its own part added, and `found`: what the step found, in sentences,
for the verdict. `whole` is all of them in order: an application as every model reads it."""

from typing import Any

from . import filefacts, sections, signals, timing, writing

App = dict[str, Any]
LETTER_MAX: int = 800  # the cover letter's first characters the content model reads


def _found(app: App, step: str, said: list[str]) -> App:
    return app | {"found": {**app.get("found", {}), step: said}}


def content(app: App) -> App:
    text = app.get("text") or {}
    resume = sections.read(text.get("resume") or text.get("letter") or text.get("email") or "")
    said = [
        f"{resume['jobs']} job{'' if resume['jobs'] == 1 else 's'} over {app.get('years', 0)} years"
        + (f", most recently {resume['recent']}" if resume["recent"] else ""),
        f"{len(resume['skills'])} skills listed" if resume["skills"] else "no skills listed",
        f"education: {resume['education'][:80]}" if resume["education"] else "no education section",
    ]
    letter = " ".join(str(text.get("letter") or "").split())[:LETTER_MAX]
    role = str(app.get("role") or "unknown")
    held = sorted({*resume["skills"], *(app.get("skills") or [])})
    resume["for_role"] = [f"{role}: {s}" for s in held]  # each skill as a skill of someone applying for this role
    resume["match"] = {
        "titles": sections.named(role, str(app.get("titles") or "")),
        "recent": sections.named(role, resume["recent"]),
        "summary": sections.named(role, f"{resume['headline']} {resume['summary']}"),
        "duties": sections.named(role, resume["duties"]),
    }
    return _found(app | {"resume": resume, "letter": letter}, "content", said)


def filed(app: App) -> App:
    file = dict(app.get("file") or filefacts.whole(filefacts.NONE, filefacts.NONE, ""))
    file["flags"] = filefacts.flags(file, str(file.pop("tools_said", "")))
    said = filefacts.found(file) or [
        f"nothing unusual in the {file['kind']} file" if file["kind"] != "none" else "no file"
    ]
    return _found(app | {"file": file}, "files", said)


def written(app: App) -> App:
    text = app.get("text") or {}
    email, letter, resume = (str(text.get(k) or "") for k in ("email", "letter", "resume"))
    measured = signals.measured(f"{email}\n\n{letter}".strip(), resume)
    parts = writing.whole(email, letter, resume)
    tells = ", ".join(t for t in measured["tells"] if t != "none")
    said = [
        f"stock phrases: {tells}" if tells else "no stock phrases",
        f"the parts stand {parts['apart']['stock']} apart on stock phrases and {parts['apart']['slips']} on slips",
    ]
    rest = {k: v for k, v in app.items() if k != "text"}
    return _found(rest | {"signals": measured, "writing": parts}, "writing", said)


def timed(app: App) -> App:
    """The timing as it was read with the email (`timing`; an application handed in without an email has none)."""
    read = app.get("timing") or timing.read("", [])
    said = timing.found(read) or ["nothing unusual in the email's timestamps"]
    return _found(app | {"timing": read}, "timing", said)


def whole(app: App) -> App:
    return written(timed(filed(content(app))))
