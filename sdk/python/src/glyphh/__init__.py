"""The Glyphh SDK for Python. Every server capability is a method here first."""

import json
import os
from dataclasses import dataclass
from typing import Literal

import httpx

from glyphh._gen.api.health import health as _health_operation
from glyphh._gen.client import Client
from glyphh._gen.models.health import Health as _HealthModel
from glyphh._gen.types import Response

__all__ = ["AsyncGlyphh", "Glyphh", "GlyphhError", "Health"]


@dataclass(frozen=True, slots=True)
class Health:
    status: Literal["ok", "degraded"]
    version: str
    database: bool


class GlyphhError(Exception):
    """A request the server refused or failed: its HTTP status (0 when the server was never reached) and its body."""

    def __init__(self, status: int, body: object) -> None:
        super().__init__(f"Glyphh request failed with status {status}")
        self.status = status
        self.body = body


def _base_url(base_url: str | None) -> str:
    url = base_url or os.environ.get("GLYPHH_URL")
    if not url:
        raise ValueError("Glyphh needs a server: pass base_url or set GLYPHH_URL")
    return url


def _body(content: bytes) -> object:
    try:
        return json.loads(content)
    except ValueError:
        return content.decode(errors="replace")


def _health(response: Response[_HealthModel]) -> Health:
    parsed = response.parsed
    if not isinstance(parsed, _HealthModel):
        raise GlyphhError(int(response.status_code), _body(response.content))
    return Health(status=parsed.status.value, version=parsed.version, database=parsed.database)


class Glyphh:
    """The Glyphh SDK, for ordinary (synchronous) code."""

    def __init__(self, base_url: str | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        args = {"transport": transport} if transport else {}
        self._client = Client(base_url=_base_url(base_url), httpx_args=args)

    def health(self) -> Health:
        """Is the server up, and can it reach its database?"""
        try:
            return _health(_health_operation.sync_detailed(client=self._client))
        except httpx.TransportError as e:
            raise GlyphhError(0, str(e)) from e


class AsyncGlyphh:
    """The Glyphh SDK, for asyncio code."""

    def __init__(self, base_url: str | None = None, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        args = {"transport": transport} if transport else {}
        self._client = Client(base_url=_base_url(base_url), httpx_args=args)

    async def health(self) -> Health:
        """Is the server up, and can it reach its database?"""
        try:
            return _health(await _health_operation.asyncio_detailed(client=self._client))
        except httpx.TransportError as e:
            raise GlyphhError(0, str(e)) from e
