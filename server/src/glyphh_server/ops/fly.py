"""Fly Machines, for the hosted runtimes: one machine and one volume per person in Glyphh's one Fly app, created
when the person first starts their runtime, started per call and stopped when idle. The Machines API, over HTTPS
with Glyphh's deploy token; a failure there is E_UNAVAILABLE `fly_failed`, never a 500."""

from typing import Any

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable

API: str = "https://api.machines.dev/v1"


class Fly:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        if not settings.fly_configured:
            raise Unavailable("Hosting isn't set up on this server.", reason="hosting_off")
        self.http, self.settings = http, settings
        self.base = f"{API}/apps/{settings.fly_app}"
        self.headers = {"authorization": f"Bearer {settings.fly_api_token}", "content-type": "application/json"}

    async def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            res = await self.http.request(method, f"{self.base}{path}", json=body, headers=self.headers)
        except httpx.HTTPError as err:
            raise Unavailable("Fly could not be reached.", reason="fly_failed", error=type(err).__name__) from err
        if res.status_code >= 400:
            raise Unavailable("Fly refused that.", reason="fly_failed", status=res.status_code, error=res.text[:200])
        return res.json() if res.content else {}

    async def create_volume(self, name: str) -> str:
        s = self.settings
        made = await self.call("POST", "/volumes", {"name": name, "region": s.fly_region, "size_gb": s.fly_volume_gb})
        return str(made["id"])

    async def create_machine(self, name: str, volume_id: str, env: dict[str, str]) -> str:
        """A stopped machine on the volume, running the hosted image; started when first called."""
        s = self.settings
        config = {
            "image": s.fly_image,
            "env": env,
            "guest": {"cpu_kind": "shared", "cpus": s.fly_cpus, "memory_mb": s.fly_memory_mb},
            "mounts": [{"volume": volume_id, "path": "/data"}],
            "restart": {"policy": "on-failure"},
            "auto_destroy": False,
        }
        made = await self.call(
            "POST", "/machines", {"name": name, "region": s.fly_region, "config": config, "skip_launch": True}
        )
        return str(made["id"])

    async def start(self, machine_id: str) -> None:
        await self.call("POST", f"/machines/{machine_id}/start")

    async def stop(self, machine_id: str) -> None:
        await self.call("POST", f"/machines/{machine_id}/stop")

    async def state(self, machine_id: str) -> str:
        return str((await self.call("GET", f"/machines/{machine_id}")).get("state", ""))

    async def destroy(self, machine_id: str, volume_id: str | None) -> None:
        await self.call("DELETE", f"/machines/{machine_id}?force=true")
        if volume_id:
            await self.call("DELETE", f"/volumes/{volume_id}")
