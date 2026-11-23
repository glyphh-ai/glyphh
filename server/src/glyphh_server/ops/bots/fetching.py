"""`fetch`, a bot's GET of JSON from one of the hosts it names: https, the host one of `spec.hosts`, then (in
ops/bots/cloud.py) every address public, no redirects, at most 5 MB. The same on Glyphh cloud and for a bot on a
rrotor, whose fetches come here."""

import urllib.parse
import urllib.request
from typing import Any

from glyphh_server.ops.bots import cloud

AGENT: str = "glyphh-bot (Glyphh's cloud)"


def fetched(spec: dict[str, Any], given: Any) -> Any:
    """A URL, or {url, headers}: the JSON it answers."""
    if isinstance(given, dict) and isinstance(given.get("url"), str):
        url, headers = given["url"], given.get("headers") if isinstance(given.get("headers"), dict) else {}
    elif isinstance(given, str):
        url, headers = given, {}
    else:
        raise ValueError('fetch takes a URL, or {"url": ..., "headers": {...}}')
    hosts = spec.get("hosts") if isinstance(spec.get("hosts"), list) else []
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError(f"{url} is not https on one of the bot's hosts ({', '.join(map(str, hosts)) or 'none'})")
    sent = {"User-Agent": AGENT, "Accept": "application/json", **{str(k): str(v) for k, v in headers.items()}}
    return cloud.fetch(urllib.request.Request(url, headers=sent), cloud.FETCH_SECONDS)
