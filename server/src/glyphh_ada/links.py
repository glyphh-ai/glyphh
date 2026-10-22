"""Short-lived signed links for files: an import's upload (PUT) and an export's download (GET). A link is its own
credential, so a person's file can be sent with `curl` and no key: it names the org, the job and what it allows, until
when, signed with the server's secret (HMAC-SHA256). Nothing in it is secret but the signature; a link that is
altered, of another kind or past its time lets nothing through (401 E_AUTH)."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from glyphh_ada.errors import NoKey

UP, DOWN = "up", "down"


@dataclass(frozen=True)
class Link:
    org: str
    model: str
    job: str
    kind: str
    expires: int
    name: str = ""  # a download's file name


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(secret: str, body: str) -> str:
    return _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def sign(secret: str, link: Link) -> str:
    claims = {"o": link.org, "m": link.model, "j": link.job, "k": link.kind, "e": link.expires, "n": link.name}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{body}.{_signature(secret, body)}"


def check(secret: str, token: str, kind: str, now: float | None = None) -> Link:
    """The link's org, model and job, if the token is one this server signed, of this kind and still live."""
    body, _, signature = token.partition(".")
    if not hmac.compare_digest(signature, _signature(secret, body)):
        raise NoKey("This link is not one of ours.")
    claims = json.loads(_unb64(body))
    link = Link(claims["o"], claims["m"], claims["j"], claims["k"], int(claims["e"]), claims["n"])
    if link.kind != kind:
        raise NoKey("This link is not for this.")
    if link.expires < (time.time() if now is None else now):
        raise NoKey("This link has expired: ask for a new one.")
    return link
