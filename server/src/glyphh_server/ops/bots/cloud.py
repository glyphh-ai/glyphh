"""What a bot's `fetch` reaches from Glyphh's side: a GET of JSON from one of the bot's hosts (https, a public
address only, no redirects, at most 5 MB). The hosts a bot names must be public names; every address a host resolves
to is checked again when it is fetched."""

import ipaddress
import json
import socket
import urllib.parse
import urllib.request
from typing import Any

from glyphh_server.errors import Invalid

FETCH_SECONDS: float = 20.0
FETCH_MAX: int = 5_000_000
PRIVATE_SUFFIXES: tuple[str, ...] = (".internal", ".local", ".localhost", ".flycast", ".lan", ".home", ".corp")


def public_host(host: str) -> bool:
    """A host name a bot may name: a DNS name with a dot, not an address, not a local or private name."""
    h = host.strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(h.strip("[]"))
        return False
    except ValueError:
        pass
    return "." in h and h != "localhost" and not h.endswith(PRIVATE_SUFFIXES)


def check_hosts(spec: dict[str, Any]) -> None:
    hosts = spec.get("hosts") or []
    bad = [h for h in hosts if isinstance(h, str) and not public_host(h)] if isinstance(hosts, list) else []
    if bad:
        raise Invalid(f"A bot fetches only from public hosts: {', '.join(bad)} is not one.", reason="hosts")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # a redirect is answered as the error it is, never followed to another host


def _resolved_public(host: str) -> bool:
    try:
        found = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    return bool(found) and all(ipaddress.ip_address(f[4][0]).is_global for f in found)


def fetch(req: urllib.request.Request, timeout: float) -> Any:
    """A fetch from the cloud: every address the host resolves to must be public, nothing redirects, and the answer
    is JSON of at most FETCH_MAX bytes."""
    host = urllib.parse.urlparse(req.full_url).hostname or ""
    if not public_host(host) or not _resolved_public(host):
        raise ValueError(f"{host} is not a public host")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(req, timeout=min(timeout, FETCH_SECONDS)) as res:
        body = res.read(FETCH_MAX + 1)
    if len(body) > FETCH_MAX:
        raise ValueError(f"{host} answered more than {FETCH_MAX // 1_000_000} MB")
    return json.loads(body)
