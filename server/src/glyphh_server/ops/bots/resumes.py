"""A resume read (ops/bots/builtins.py): its text from the file it came in (PDF, Word's DOCX or plain text) and the
fields its decisions' Ada models read of it: the applicant's name and email, their years of work (the spans of the
dates on it, overlaps counted once), their skills (the resume's own skills lines and the common skills named
anywhere in it), the titles they held and their highest degree. Deterministic code, no model: what it reads is
what the resume says."""

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

TEXT_MAX: int = 60_000
PAGES_MAX: int = 20
DOCX_XML_MAX: int = 10_000_000
W: str = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EMAIL: re.Pattern[str] = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DASHES: str = chr(0x2013) + chr(0x2014)  # the en and em dashes a date span is written with
SPAN: re.Pattern[str] = re.compile(
    rf"\b((?:19|20)\d{{2}})\s*(?:-|[{DASHES}]|to)\s*((?:19|20)\d{{2}}|present|current|now)\b", re.I
)
SAID_YEARS: re.Pattern[str] = re.compile(r"\b(\d{1,2})\+?\s+years?\b", re.I)
SKILLS_LINE: re.Pattern[str] = re.compile(r"^\s*(?:technical\s+)?skills?\s*[:\-]\s*(.+)$", re.I | re.M)
NOW: int = 2026
SKILLS: tuple[str, ...] = (
    *("python", "java", "typescript", "javascript", "react", "next.js", "graphql", "css", "html", "sql"),
    *("postgres", "redis", "kafka", "kubernetes", "terraform", "aws", "gcp", "azure", "grpc", "docker", "rust"),
    *("distributed systems", "testing", "accessibility", "performance", "storybook", "webpack", "figma"),
    *("user research", "prototyping", "design systems", "interaction design", "motion design", "usability testing"),
    *("dashboards", "statistics", "excel", "dbt", "looker", "tableau", "a/b testing", "bigquery", "salesforce"),
    *("customer onboarding", "renewals", "account management", "churn reduction", "zendesk", "gainsight", "saas"),
)
DEGREES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("phd", ("ph.d", "phd", "doctorate")),
    ("masters", ("m.sc", "master", "mba", "m.s.", "m.eng")),
    ("bachelors", ("b.sc", "bachelor", "b.a.", "b.s.", "b.eng", "bsc", "b.tech")),
)


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:PAGES_MAX])


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > DOCX_XML_MAX:
            raise ValueError("the document is too big to read")
        root = ET.fromstring(z.read(info))
    return "\n".join("".join(t.text or "" for t in p.iter(f"{W}t")) for p in root.iter(f"{W}p"))


def text(kind: str, data: bytes) -> str:
    """The file's text, at most TEXT_MAX characters; a file that cannot be read is ValueError, saying so."""
    try:
        got = _pdf(data) if kind == "pdf" else _docx(data) if kind == "docx" else data.decode("utf-8", "replace")
    except Exception as err:  # any parser's failure on a bad file is the same answer: unreadable
        raise ValueError(f"the {kind} file could not be read: {type(err).__name__}") from err
    return got[:TEXT_MAX]


def years(said: str) -> int:
    """Years of work: the date spans on it merged (overlaps counted once), else the most years it says outright."""
    spans = []
    for start, end in SPAN.findall(said):
        stop = NOW if not end[:1].isdigit() else int(end)
        if int(start) <= stop <= NOW:
            spans.append((int(start), stop))
    total, reach = 0, 0
    for start, stop in sorted(spans):
        start = max(start, reach)
        if stop > start:
            total, reach = total + stop - start, stop
    if total == 0:
        total = max((int(n) for n in SAID_YEARS.findall(said)), default=0)
    return min(total, 50)


def skills(said: str) -> list[str]:
    listed = [s.strip(" .").lower() for line in SKILLS_LINE.findall(said) for s in re.split(r"[,;|•·]", line)]
    lower = said.lower()
    named = [s for s in SKILLS if re.search(rf"(?<![\w.]){re.escape(s)}(?![\w])", lower)]
    return sorted({s for s in listed + named if 0 < len(s) <= 40})[:40]


def titles(said: str) -> str:
    """The titles held: the text before the employer on each line that carries a date span."""
    found = [re.split(r",| at | @ |\(", line, maxsplit=1)[0].strip(" -•") for line in said.splitlines()
             if SPAN.search(line)]  # fmt: skip
    return "; ".join(t for t in found if t)[:500]


def education(said: str) -> str:
    lower = said.lower()
    return next((level for level, words in DEGREES if any(w in lower for w in words)), "none")


def fields(said: str, sender_name: str, sender_email: str) -> dict[str, Any]:
    first = next((line.strip() for line in said.splitlines() if line.strip()), "")
    looks_named = 1 < len(first.split()) <= 4 and all(w[:1].isupper() for w in first.split()) and "@" not in first
    email = EMAIL.search(said)
    return {
        "name": first if looks_named else sender_name,
        "email": email.group(0).lower() if email else sender_email,
        "years": years(said),
        "skills": skills(said),
        "titles": titles(said),
        "education": education(said),
    }
