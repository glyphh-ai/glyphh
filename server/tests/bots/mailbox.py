"""A Gmail inbox of job applications, faked behind Pipedream's Connect proxy (the server's own client calls it
unchanged): messages with their headers, text and attachments (a PDF and a Word resume made here, byte for byte as
those files are), the labels made and put on them. And the files themselves: a one-page PDF and a DOCX."""

import base64
import io
import json
import zipfile
from typing import Any

import httpx

from tests.bots.fakes import CONNECT, FakePipedream

GMAIL: str = "https://gmail.googleapis.com/gmail/v1/users/me"


def pdf(lines: list[str]) -> bytes:
    """A real one-page PDF of these lines (Helvetica), its cross-reference table and all."""
    text = "\n".join(f"({ln.replace('(', '[').replace(')', ']')}) Tj 0 -14 Td" for ln in lines)
    stream = f"BT /F1 11 Tf 50 750 Td\n{text}\nET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> "
            b"/Contents 4 0 R >>", b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]  # fmt: skip
    out, offsets = io.BytesIO(b"%PDF-1.4\n"), []
    out.seek(0, 2)
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def docx(paragraphs: list[str]) -> bytes:
    """A real Word document of these paragraphs (the parts Word needs to open it)."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body>{body}'
                   "</w:body></w:document>")  # fmt: skip
    return out.getvalue()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


Files = tuple[tuple[str, bytes], ...]
Heads = tuple[tuple[str, str], ...]
PASS: str = "spf=pass dkim=pass dmarc=pass"


def message(
    mid: str, sender: str, subject: str, text: str, auth: str = PASS, files: Files = (), extra: Heads = ()
) -> dict[str, Any]:
    """A message as Gmail's API answers format=full; `extra` more headers, `files` its attachments."""
    heads = [{"name": "From", "value": sender}, {"name": "Subject", "value": subject},
             {"name": "Authentication-Results", "value": f"mx.google.com; {auth}"}]  # fmt: skip
    parts = [{"mimeType": "text/plain", "filename": "", "body": {"data": b64(text.encode()), "size": len(text)}}]
    for i, (name, data) in enumerate(files):
        body = {"attachmentId": f"{mid}-{i}", "size": len(data)}
        parts.append({"mimeType": "application/octet-stream", "filename": name, "body": body})
    payload = {"mimeType": "multipart/mixed", "headers": heads + [{"name": n, "value": v} for n, v in extra],
               "parts": parts}  # fmt: skip
    return {"id": mid, "payload": payload, "_files": {f"{mid}-{i}": data for i, (_, data) in enumerate(files)}}


class FakeGmail(FakePipedream):
    """FakePipedream with an inbox behind its proxy: `inbox` the messages (those labelled Screened left out of a
    search for -label:screened), `labels` made, `marked` the labels put on each message, `proxied` each URL asked."""

    def __init__(self) -> None:
        super().__init__()
        self.inbox: list[dict[str, Any]] = []
        self.labels: dict[str, str] = {}
        self.marked: dict[str, set[str]] = {}
        self.proxied: list[tuple[str, str, Any]] = []

    def _connect(self, method: str, path: str, body: Any, query: dict[str, str]) -> httpx.Response:
        if not path.startswith(f"{CONNECT}/proxy/"):
            return super()._connect(method, path, body, query)
        url = base64.urlsafe_b64decode(path.rsplit("/", 1)[1] + "==").decode()
        self.proxied.append((method, url, query))
        return httpx.Response(200, json=self._gmail(method, url.removeprefix(GMAIL), body))

    def _gmail(self, method: str, rest: str, body: Any) -> Any:
        route, _, q = rest.partition("?")
        parts = route.strip("/").split("/")
        if route == "/messages":
            screened = "-label%3Ascreened" in q
            found = [m for m in self.inbox if not (screened and "Screened" in self.marked.get(m["id"], set()))]
            return {"messages": [{"id": m["id"]} for m in found]}
        if route == "/labels" and method == "GET":
            return {"labels": [{"id": i, "name": n} for n, i in self.labels.items()]}
        if route == "/labels":
            self.labels[body["name"]] = f"L{len(self.labels) + 1}"
            return {"id": self.labels[body["name"]], "name": body["name"]}
        if route == "/messages/batchModify":
            names = {i: n for n, i in self.labels.items()}
            for mid in body["ids"]:
                self.marked.setdefault(mid, set()).update(names[i] for i in body["addLabelIds"])
            return None
        found = next(m for m in self.inbox if m["id"] == parts[1])
        if len(parts) == 4:  # messages/<id>/attachments/<id>
            return {"data": b64(found["_files"][parts[3]])}
        return json.loads(json.dumps({k: v for k, v in found.items() if k != "_files"}))
