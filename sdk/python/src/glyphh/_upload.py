"""Sending a picture (a listing's icon or a screenshot) as its own bytes: the generated client has no call for a
binary body, so this is one, with the same shape the other calls answer in."""

import json
from http import HTTPStatus
from typing import Any

import httpx

from glyphh._gen.client import Client
from glyphh._gen.types import Response


def _answer(res: httpx.Response) -> Response[Any]:
    parsed = json.loads(res.content) if res.content else None
    return Response(status_code=HTTPStatus(res.status_code), content=res.content, headers=res.headers, parsed=parsed)


def _request(path: str, data: bytes, content_type: str, name: str) -> dict[str, Any]:
    return {"url": path, "content": data, "headers": {"content-type": content_type, "x-file-name": name}}


class Upload:
    """An operation the SDK's calls run like a generated one: PUT the icon or POST a screenshot."""

    def __init__(self, method: str, suffix: str) -> None:
        self.method = method
        self.suffix = suffix

    def sync_detailed(
        self, *, client: Client, listing_id: str, data: bytes, content_type: str, name: str
    ) -> Response[Any]:
        req = _request(f"/v1/listings/{listing_id}/{self.suffix}", data, content_type, name)
        return _answer(client.get_httpx_client().request(self.method, **req))

    async def asyncio_detailed(
        self, *, client: Client, listing_id: str, data: bytes, content_type: str, name: str
    ) -> Response[Any]:
        req = _request(f"/v1/listings/{listing_id}/{self.suffix}", data, content_type, name)
        return _answer(await client.get_async_httpx_client().request(self.method, **req))


class ProviderLogo:
    """Glyphh admin's PUT of a provider's logo (or its copy for dark grounds), run like a generated operation."""

    @staticmethod
    def _path(provider_id: str, dark: bool) -> str:
        return f"/v1/admin/providers/{provider_id}/logo?dark={'true' if dark else 'false'}"

    def sync_detailed(
        self, *, client: Client, provider_id: str, data: bytes, content_type: str, name: str, dark: bool
    ) -> Response[Any]:
        req = _request(self._path(provider_id, dark), data, content_type, name)
        return _answer(client.get_httpx_client().request("PUT", **req))

    async def asyncio_detailed(
        self, *, client: Client, provider_id: str, data: bytes, content_type: str, name: str, dark: bool
    ) -> Response[Any]:
        req = _request(self._path(provider_id, dark), data, content_type, name)
        return _answer(await client.get_async_httpx_client().request("PUT", **req))


SET_ICON = Upload("PUT", "icon")
SET_PROVIDER_LOGO = ProviderLogo()
ADD_SCREENSHOT = Upload("POST", "screenshots")
