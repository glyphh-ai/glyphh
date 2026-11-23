"""An application as the Resume Screener's decisions read it (ops/bots/builtins.py): one email (or a resume the person
hands it) made into one item: who sent it and whether their domain vouched for it (SPF, DKIM, DMARC), whether it was
sent in bulk, the role it is for (from its subject), the resume's fields (ops/bots/resumes.py) and how its words
were written (ops/bots/signals.py). The hard checks come first, in code: a message whose sender's domain did not
vouch for it (SPF failed and no DKIM passed), with no sender, or with nothing to screen is never an applicant, and
says why; the rest go to Ada."""

import re
from email.utils import parseaddr
from typing import Any

from glyphh_server.ops.bots import resumes, signals

AUTH: re.Pattern[str] = re.compile(r"\b(spf|dkim|dmarc)=(\w+)", re.I)
FREE: frozenset[str] = frozenset(
    ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com", "me.com",
     "proton.me", "protonmail.com", "fastmail.com", "hey.com", "aol.com", "gmx.com", "zoho.com", "yandex.com")
)  # fmt: skip
NOISE: re.Pattern[str] = re.compile(
    rf"\b(re|fwd?|application|applying|apply|job|for|role|position|the|to|as)\b|[:\-|{resumes.DASHES}]", re.I
)
OPENING: int = 300


def authed(said: str) -> dict[str, str]:
    """Each of SPF, DKIM and DMARC as the receiving server found it (a pass anywhere counts); `none` when unsaid."""
    found = {"spf": "none", "dkim": "none", "dmarc": "none"}
    for what, result in AUTH.findall(said):
        what, result = what.lower(), result.lower()
        if found[what] == "none" or result == "pass":
            found[what] = result
    return found


def sender(from_header: str) -> tuple[str, str, str, str]:
    """(name, email, domain, kind): kind `free` (a webmail), `edu`, `company` or `unknown`."""
    name, email = parseaddr(from_header)
    email = email.lower()
    domain = email.rsplit("@", 1)[1] if "@" in email else ""
    kind = "unknown" if not domain else "free" if domain in FREE else "edu" if ".edu" in domain else "company"
    return name or email.split("@")[0], email, domain, kind


def role_of(subject: str, name: str) -> str:
    words = NOISE.sub(" ", subject)
    for part in name.split():
        words = re.sub(rf"\b{re.escape(part)}\b", " ", words, flags=re.I)
    return " ".join(words.split()).lower() or "unknown"


def refused(auth: dict[str, str], email: str, body: str, resume: str) -> str | None:
    if not email:
        return "it has no sender"
    if auth["spf"] in ("fail", "softfail") and auth["dkim"] != "pass":
        return "the sender's domain did not vouch for it (SPF failed and no DKIM signature passed)"
    if not body.strip() and not resume.strip():
        return "there is nothing in it to screen"
    return None


def item(mid: str, from_header: str, subject: str, auth_said: str, bulk: bool, body: str, resume: str,
         resume_kind: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:  # fmt: skip
    """(the applicant, None), or (None, why it is not one)."""
    name, email, domain, kind = sender(from_header)
    auth = authed(auth_said) if auth_said != "given" else {"spf": "given", "dkim": "given", "dmarc": "given"}
    why = refused(auth, email or ("given" if auth_said == "given" else ""), body, resume)
    if why:
        return None, {"id": mid, "from": email, "subject": subject, "why": why}
    read = resumes.fields(resume or body, name, email)
    role = role_of(subject, read["name"])
    made = {
        "id": mid, "label": f"{read['name']} - {role}", "subject": subject, "from": email, "domain": domain or "none",
        "sender_kind": kind, "auth": [f"{k}:{v}" for k, v in auth.items()], "bulk": "yes" if bulk else "no",
        "has_resume": "yes" if resume.strip() else "no", "resume_kind": resume_kind if resume.strip() else "none",
        "role": role, "opening": " ".join(body.split())[:OPENING], **read, "signals": signals.measured(body, resume),
    }  # fmt: skip
    return made, None


def bulk_of(headers: dict[str, str]) -> bool:
    auto = headers.get("auto-submitted", "no").lower()
    return "list-unsubscribe" in headers or headers.get("precedence", "").lower() in ("bulk", "list") or auto != "no"


def of_mail(mail: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """An email read from the inbox (ops/bots/gmail.py), its first readable attachment the resume."""
    h = mail.headers
    resume, kind, problems = "", "none", []
    for name, file_kind, data in mail.files:
        try:
            resume, kind = resumes.text(file_kind, data), file_kind
            break
        except ValueError as err:
            problems.append(f"{name}: {err}")
    spf = h.get("received-spf", "").split(" ", 1)[0]
    auth = h.get("authentication-results", "") + (f" spf={spf}" if spf else "")
    got, why = item(mail.id, h.get("from", ""), h.get("subject", ""), auth, bulk_of(h), mail.text, resume, kind)
    if got is not None and problems:
        got["resume_problems"] = problems
    return got, why


def of_given(mid: str, given: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """A resume (or a whole application) the person hands the screener: no inbox, so no sender checks."""
    resume, sent = str(given.get("resume") or ""), str(given.get("sender") or "")
    subject = str(given.get("role") or "") or "unknown"
    return item(mid, sent, subject, "given", False, str(given.get("letter") or ""), resume, "text")
