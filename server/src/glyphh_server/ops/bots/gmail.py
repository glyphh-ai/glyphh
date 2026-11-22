"""The org's Gmail as Glyphh's built-in tools read it (ops/bots/builtins.py): Gmail's own API through Pipedream's
Connect proxy, as the connection's account. A message is read whole (its headers, its text, its attachments' bytes,
each at most ATTACHMENT_MAX and only the kinds a resume comes in), and messages are labelled once screened, so the
next poll leaves them out and the person sees each verdict in their inbox."""

import base64
import html
import re
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Any

from glyphh_server.ops.bots.pipedream import Pipedream

API: str = "https://gmail.googleapis.com/gmail/v1/users/me"
ATTACHMENT_MAX: int = 5_000_000
KINDS: dict[str, str] = {".pdf": "pdf", ".docx": "docx", ".txt": "text", ".md": "text"}
TAG: re.Pattern[str] = re.compile(r"<[^>]+>")


@dataclass
class Mail:
    """One message as read: its id, headers (lower-cased names; a repeated one's values joined), text and files."""

    id: str
    headers: dict[str, str]
    text: str
    files: list[tuple[str, str, bytes]] = field(default_factory=list)  # (name, kind, bytes)


def unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def kind_of(name: str) -> str | None:
    dot = name.lower().rfind(".")
    return KINDS.get(name.lower()[dot:]) if dot >= 0 else None


def _parts(part: dict[str, Any]) -> list[dict[str, Any]]:
    inner = part.get("parts") or []
    return [part] + [p for child in inner for p in _parts(child)]


def headers(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in payload.get("headers") or []:
        name = str(h.get("name", "")).lower()
        out[name] = f"{out[name]}; {h.get('value', '')}" if name in out else str(h.get("value", ""))
    return out


def text_of(payload: dict[str, Any]) -> str:
    """The message's plain text: its text/plain parts, else its HTML with the tags taken out."""
    parts = [p for p in _parts(payload) if not p.get("filename")]
    plain = [unb64(p["body"]["data"]).decode("utf-8", "replace") for p in parts
             if p.get("mimeType") == "text/plain" and (p.get("body") or {}).get("data")]  # fmt: skip
    if plain:
        return "\n".join(plain)
    rich = [unb64(p["body"]["data"]).decode("utf-8", "replace") for p in parts
            if p.get("mimeType") == "text/html" and (p.get("body") or {}).get("data")]  # fmt: skip
    return html.unescape(TAG.sub(" ", "\n".join(rich)))


class Gmail:
    def __init__(self, pd: Pipedream, org_id: uuid.UUID, account_id: str) -> None:
        self.pd, self.org_id, self.account_id = pd, org_id, account_id

    async def _get(self, path: str, **query: Any) -> Any:
        url = f"{API}{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
        return await self.pd.proxy(self.org_id, self.account_id, "GET", url) or {}

    async def _post(self, path: str, body: Any) -> Any:
        return await self.pd.proxy(self.org_id, self.account_id, "POST", f"{API}{path}", body) or {}

    async def ids(self, q: str, most: int) -> list[str]:
        found = await self._get("/messages", q=q, maxResults=most)
        return [str(m["id"]) for m in found.get("messages") or []][:most]

    async def read(self, message_id: str) -> Mail:
        got = await self._get(f"/messages/{message_id}", format="full")
        payload = got.get("payload") or {}
        mail = Mail(message_id, headers(payload), text_of(payload))
        for p in _parts(payload):
            name, body = str(p.get("filename") or ""), p.get("body") or {}
            kind = kind_of(name)
            if not kind or int(body.get("size") or 0) > ATTACHMENT_MAX:
                continue
            data = body.get("data")
            if not data and body.get("attachmentId"):
                data = (await self._get(f"/messages/{message_id}/attachments/{body['attachmentId']}")).get("data")
            if data:
                mail.files.append((name, kind, unb64(data)[:ATTACHMENT_MAX]))
        return mail

    async def _label_ids(self, names: list[str]) -> dict[str, str]:
        have = {lab["name"]: lab["id"] for lab in (await self._get("/labels")).get("labels") or []}
        for name in names:
            if name not in have:
                made = await self._post("/labels", {"name": name, "labelListVisibility": "labelShow",
                                                    "messageListVisibility": "show"})  # fmt: skip
                have[name] = made["id"]
        return have

    async def label(self, marks: dict[str, list[str]]) -> dict[str, int]:
        """Each label put on its messages ({label: [message id]}), the labels made where missing."""
        ids = await self._label_ids(sorted(marks))
        for name, messages in marks.items():
            await self._post("/messages/batchModify", {"ids": messages, "addLabelIds": [ids[name]]})
        return {name: len(messages) for name, messages in marks.items()}
