"""Cloudflare's API, read only, for Glyphh's own sites' traffic (ops/traffic.py): the zones the token sees and the
GraphQL Analytics API. Every failure is a CloudflareError of a kind (unreachable, auth, rate, refused, query) whose
message is Cloudflare's own words, never the token."""

from typing import Any

import httpx

API: str = "https://api.cloudflare.com/client/v4"
PAGE: int = 50


class CloudflareError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def _messages(body: Any) -> str:
    errors = body.get("errors") if isinstance(body, dict) else None
    return "; ".join(str(e.get("message", e)) for e in errors or [] if isinstance(e, dict))[:300]


class Cloudflare:
    def __init__(self, http: httpx.AsyncClient, token: str) -> None:
        self.http = http
        self.headers = {"authorization": f"Bearer {token}"}

    async def _send(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        try:
            res = await self.http.request(method, f"{API}{path}", headers=self.headers, timeout=30, **kw)
        except httpx.HTTPError as err:
            raise CloudflareError("unreachable", f"Cloudflare could not be reached ({type(err).__name__})") from err
        try:
            body = res.json()
        except ValueError:
            body = {}
        if res.status_code == 429:
            raise CloudflareError("rate", "Cloudflare's rate limit")
        if res.status_code in (401, 403):
            raise CloudflareError("auth", f"Cloudflare refused the token: {_messages(body)}")
        if res.status_code >= 400 or not isinstance(body, dict):
            raise CloudflareError("refused", f"Cloudflare answered {res.status_code}: {_messages(body)}")
        return body

    async def zones(self) -> list[dict[str, Any]]:
        """Every zone the token sees: id, name, plan and account."""
        found: list[dict[str, Any]] = []
        page = 1
        while True:
            body = await self._send("GET", "/zones", params={"per_page": PAGE, "page": page})
            found += body.get("result") or []
            if page >= int((body.get("result_info") or {}).get("total_pages") or 1):
                return found
            page += 1

    async def query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """One GraphQL query's data; its errors raised (a rate limit as one)."""
        body = await self._send("POST", "/graphql", json={"query": query, "variables": variables})
        if body.get("errors"):
            words = _messages(body)
            raise CloudflareError("rate" if "rate limit" in words.lower() else "query", words)
        return body.get("data") or {}
