"""Calls to a provider, failing closed: anything but a good answer is the provider being unavailable."""

import logging
from typing import Any

import httpx

from glyphh_server.errors import Unavailable
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.auth.provider")


async def json_call(http: httpx.AsyncClient, provider: str, method: str, url: str, **kwargs: Any) -> Any:
    try:
        res = await http.request(method, url, **kwargs)
        res.raise_for_status()
        return res.json()
    except (httpx.HTTPError, ValueError) as err:
        log.warning("provider call failed", extra=fields(provider=provider, url=url, error=repr(err)))
        raise Unavailable(f"Signing in with {provider} didn't work. Try again.", provider=provider) from err
