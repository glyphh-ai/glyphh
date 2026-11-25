"""A resume split into its sections (the Resume Screener's content check): what stands before
the first heading (the name, the contact line, a headline), the summary, the experience as its entries (each line
that carries a date span: the title before the employer, the employer, the years it spans), the education and the
skills as the terms listed. A heading is a line that is only the section's name (Experience, Work Experience,
Skills, ...), with or without a colon, or the name, a colon and the section's first line (Skills: sql, excel). A
resume with no headings is all `head`, and its entries are still found by their date spans."""

import re
from typing import Any

from . import resumes

NAMES: dict[str, str] = {
    "summary": "summary", "profile": "summary", "professional summary": "summary", "objective": "summary",
    "about": "summary", "about me": "summary",
    "experience": "experience", "work experience": "experience", "professional experience": "experience",
    "employment": "experience", "employment history": "experience", "work history": "experience",
    "education": "education", "education and training": "education",
    "skills": "skills", "technical skills": "skills", "core skills": "skills", "key skills": "skills",
}  # fmt: skip
HEADING: re.Pattern[str] = re.compile(rf"^\s*({'|'.join(sorted(NAMES, key=len, reverse=True))})\s*(?::\s*(.*))?$", re.I)
TERMS: re.Pattern[str] = re.compile(r"[,;|•·\n]")
LEVELS: frozenset[str] = frozenset(("senior", "junior", "lead", "staff", "principal", "associate", "head", "intern"))
SUMMARY_MAX, WORDS_MAX, TERMS_MAX, ENTRIES_MAX = 600, 1500, 40, 12


def split(resume: str) -> dict[str, str]:
    """The resume's text by section: head, summary, experience, education, skills (each may be empty)."""
    parts: dict[str, list[str]] = {"head": [], "summary": [], "experience": [], "education": [], "skills": []}
    at = "head"
    for line in resume.splitlines():
        found = HEADING.match(line)
        if found:
            at, line = NAMES[found.group(1).lower()], found.group(2) or ""
        parts[at].append(line)
    return {name: "\n".join(lines).strip() for name, lines in parts.items()}


def entries(experience: str) -> list[dict[str, Any]]:
    """The jobs held: each line with a date span, as its title, its employer, the years it spans and the span
    itself (`2019-2021`, `2021-present`)."""
    out = []
    for line in experience.splitlines():
        span = resumes.SPAN.search(line)
        if span:
            title, _, rest = line[: span.start()].strip(" -•").partition(",")
            dates = f"{span.group(1)}-{span.group(2).lower()}"
            job = {"title": title.strip(), "employer": rest.strip(" ,-"), "years": resumes.years(line), "span": dates}
            out.append(job)
    return out[:ENTRIES_MAX]


def terms(skills: str) -> list[str]:
    found = [t.strip(" .-").lower() for t in TERMS.split(skills)]
    return sorted({t for t in found if 0 < len(t) <= 40})[:TERMS_MAX]


def named(role: str, said: str) -> int:
    """How much of the role's name a part says, 0 to 100: the share of the role's own words (its level left out)
    that stand in it. A backend engineer's titles say `backend engineer`; a paralegal's do not."""
    words = {w for w in re.findall(r"[a-z]+", role.lower()) if w not in LEVELS and len(w) > 2}
    there = set(re.findall(r"[a-z]+", said.lower()))
    return round(100 * len(words & there) / len(words)) if words else 0


def read(resume: str) -> dict[str, Any]:
    """The resume as the content model reads it: each section's part, short enough to be handed on."""
    parts = split(resume)
    jobs = entries(parts["experience"] or resume)
    duties = [ln.strip(" -•") for ln in parts["experience"].splitlines() if ln.strip() and not resumes.SPAN.search(ln)]
    return {
        "headline": " ".join(parts["head"].split("\n")[2:3])[:200],
        "summary": " ".join(parts["summary"].split())[:SUMMARY_MAX],
        "titles": [j["title"] for j in jobs if j["title"]],
        "recent": jobs[0]["title"] if jobs else "",
        "employers": [j["employer"] for j in jobs if j["employer"]],
        "jobs": len(jobs),
        "duties": " ".join(duties)[:WORDS_MAX],
        "education": " ".join(parts["education"].split())[:300],
        "skills": terms(parts["skills"]) or resumes.skills(resume),
    }
