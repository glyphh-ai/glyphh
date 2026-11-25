"""An email as the screener reads one: its headers (every `Received` line kept, in the order the message has them:
the last server first), its words and its readable attachments, each as (name, kind, bytes). `read` takes a whole
message (an .eml file, or a message's source pasted as text); `pasted` takes what a person has when they have no
source: the email's words, with or without header lines above them, and the files beside it. Nothing is written
anywhere: a message is read from the bytes it is given."""

import email
import re
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage

HEADER: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s?\S")
KINDS: dict[str, str] = {".pdf": "pdf", ".docx": "docx", ".txt": "text", ".md": "text"}
File = tuple[str, str, bytes]


@dataclass
class Mail:
    id: str
    headers: dict[str, str]
    text: str
    files: list[File] = field(default_factory=list)
    received: list[str] = field(default_factory=list)  # every Received header, the last hop first
    date: str = ""


def kind_of(name: str, data: bytes) -> str | None:
    """A file's kind from what it starts with, else from its name; None: not a file the screener reads."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK":
        return "docx"
    return next((kind for end, kind in KINDS.items() if name.lower().endswith(end)), None)


def _files(msg: EmailMessage) -> list[File]:
    out = []
    for part in msg.walk():
        name = part.get_filename()
        data = part.get_payload(decode=True) if name else None
        if name and isinstance(data, bytes) and (kind := kind_of(str(name), data)):
            out.append((str(name), kind, data))
    return out


def _words(msg: EmailMessage) -> str:
    plain = [p for p in msg.walk() if p.get_content_type() == "text/plain" and not p.get_filename()]
    return "\n".join(str(p.get_content()) for p in plain)


def read(raw: bytes, mid: str = "") -> Mail:
    """A whole message, as a mail server or an .eml file holds it."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)
    headers = {k.lower(): " ".join(str(v).split()) for k, v in msg.items()}
    received = [" ".join(str(v).split()) for v in (msg.get_all("received") or [])]
    return Mail(mid or headers.get("message-id", "").strip("<>") or "given", headers, _words(msg), _files(msg),
                received, headers.get("date", ""))  # fmt: skip


def pasted(text: str, files: list[tuple[str, bytes]], mid: str = "given") -> Mail:
    """The email as a person pasted it, and the files they attached. When the text begins with header lines (its
    source was pasted), they are read as headers; otherwise it is all the email's words and nothing is known of
    how it travelled."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    if HEADER.match(first) and re.search(r"^(from|date|received|subject):", text, re.I | re.M):
        got = read(text.lstrip().encode("utf-8", "replace"), mid)
    else:
        got = Mail(mid, {}, text)
    more = [(name, kind, data) for name, data in files if (kind := kind_of(name, data))]
    got.files = got.files + more
    return got
