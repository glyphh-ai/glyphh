"""Pipedream Connect (docs/specs/bots.md, Connections), over the server's HTTP client: an org is one external user
(`org_<id>`) of Glyphh's Pipedream project, its accounts are signed in on Pipedream's own page (a Connect link), and a
bot's tool is a Pipedream action run as the org with one of its accounts. The server holds no one's sign-in, only
Pipedream's account ids. The project's OAuth client mints the access token, kept until a minute before it ends."""

import time
import uuid
from typing import Any

import httpx

from glyphh_server.bot_settings import BotSettings
from glyphh_server.errors import Invalid, Unavailable

API: str = "https://api.pipedream.com/v1"
OFF: str = "Connections are not set up on this server (Pipedream)."


def external_user(org_id: uuid.UUID) -> str:
    return f"org_{org_id}"


class Pipedream:
    def __init__(self, http: httpx.AsyncClient, settings: BotSettings) -> None:
        self.http = http
        self.settings = settings
        self._token = ""
        self._until = 0.0

    @property
    def on(self) -> bool:
        return self.settings.pipedream_on

    async def _bearer(self) -> str:
        if not self.on:
            raise Unavailable(OFF, reason="pipedream_off")
        if self._token and time.monotonic() < self._until:
            return self._token
        cfg = self.settings
        sent = {
            "grant_type": "client_credentials",
            "client_id": cfg.pipedream_client_id,
            "client_secret": cfg.pipedream_client_secret,
        }
        answer = await self._send("POST", f"{API}/oauth/token", json=sent, auth=False)
        self._token = answer["access_token"]
        self._until = time.monotonic() + max(0, int(answer.get("expires_in", 3600)) - 60)
        return self._token

    async def _send(self, method: str, url: str, auth: bool = True, **kwargs: Any) -> Any:
        headers = {"x-pd-environment": self.settings.pipedream_environment}
        if auth:
            headers["authorization"] = f"Bearer {await self._bearer()}"
        try:
            res = await self.http.request(method, url, headers=headers, timeout=60, **kwargs)
        except httpx.HTTPError as err:
            raise Unavailable("Pipedream did not answer.", reason="pipedream") from err
        if res.status_code == 204 or not res.content:
            return None
        if res.status_code >= 400:
            said = res.text[:500]
            if res.status_code >= 500:
                raise Unavailable(f"Pipedream failed: {said}", reason="pipedream")
            raise Invalid(f"Pipedream refused: {said}", reason="pipedream", status=res.status_code)
        return res.json()

    def _connect(self, path: str) -> str:
        return f"{API}/connect/{self.settings.pipedream_project_id}{path}"

    async def link(self, org_id: uuid.UUID, app: str) -> dict[str, Any]:
        """A Connect link where someone in the org signs in to `app` for the org."""
        made = await self._send("POST", self._connect("/tokens"), json={"external_user_id": external_user(org_id)})
        url = httpx.URL(made["connect_link_url"]).copy_merge_params({"app": app})
        return {"url": str(url), "expires_at": made.get("expires_at")}

    async def accounts(self, org_id: uuid.UUID) -> list[dict[str, Any]]:
        params = {"external_user_id": external_user(org_id), "limit": 100}
        return (await self._send("GET", self._connect("/accounts"), params=params) or {}).get("data", [])

    async def forget(self, account_id: str) -> None:
        await self._send("DELETE", self._connect(f"/accounts/{account_id}"))

    async def apps(self, q: str | None, cursor: str | None) -> dict[str, Any]:
        params = {k: v for k, v in {"q": q, "after": cursor, "limit": 30}.items() if v}
        return await self._send("GET", f"{API}/apps", params=params) or {}

    async def actions(self, app: str) -> list[dict[str, Any]]:
        params = {"app": app, "limit": 100}
        return (await self._send("GET", self._connect("/actions"), params=params) or {}).get("data", [])

    async def component(self, key: str) -> dict[str, Any]:
        return (await self._send("GET", self._connect(f"/components/{key}")) or {}).get("data", {})

    async def run(self, org_id: uuid.UUID, key: str, props: dict[str, Any]) -> Any:
        sent = {"id": key, "external_user_id": external_user(org_id), "configured_props": props}
        return await self._send("POST", self._connect("/actions/run"), json=sent)
