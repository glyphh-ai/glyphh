"""GitHub's REST API, read only, for the traffic of Glyphh's public repositories (ops/traffic/github.py): a repository's
views and clones by day and its popular referrers and paths, the last 14 days as GitHub keeps them. Every failure is a
GitHubError of a kind (unreachable, auth, rate, refused) whose message is GitHub's own words, never the token."""

from typing import Any

import httpx

API: str = "https://api.github.com"
VERSION: str = "2022-11-28"


class GitHubError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class GitHub:
    def __init__(self, http: httpx.AsyncClient, token: str) -> None:
        self.http = http
        self.headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": VERSION,
        }

    async def get(self, path: str, **params: Any) -> Any:
        """One GET's JSON; its failure raised."""
        try:
            res = await self.http.get(f"{API}{path}", headers=self.headers, params=params, timeout=30)
        except httpx.HTTPError as err:
            raise GitHubError("unreachable", f"GitHub could not be reached ({type(err).__name__})") from err
        try:
            body = res.json()
        except ValueError:
            body = None
        words = str(body.get("message") or "")[:300] if isinstance(body, dict) else ""
        if res.status_code == 429 or (res.status_code == 403 and res.headers.get("x-ratelimit-remaining") == "0"):
            raise GitHubError("rate", "GitHub's rate limit")
        if res.status_code in (401, 403):
            raise GitHubError("auth", f"GitHub refused the token: {words}")
        if res.status_code >= 400 or body is None:
            raise GitHubError("refused", f"GitHub answered {res.status_code}: {words}")
        return body

    async def traffic(self, repo: str, part: str) -> Any:
        """A repository's traffic: views or clones (by day), popular/referrers or popular/paths."""
        params = {"per": "day"} if part in ("views", "clones") else {}
        return await self.get(f"/repos/{repo}/traffic/{part}", **params)
