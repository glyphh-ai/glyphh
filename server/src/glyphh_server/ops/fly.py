"""Fly Machines, for the hosted runtimes: each a machine and its volume in Glyphh's one Fly app, of the size the person
chose (models/rrotor.py SIZES: the guest and the volume), started per call and stopped when idle. The Machines API, over
HTTPS with Glyphh's deploy token; a failure there is E_UNAVAILABLE `fly_failed`, never a 500."""

from typing import Any

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.models.rrotor import SIZES, Size

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

    async def create_volume(self, name: str, size: Size) -> str:
        body = {"name": name, "region": self.settings.fly_region, "size_gb": size.volume_gb}
        return str((await self.call("POST", "/volumes", body))["id"])

    async def list_machines(self) -> list[dict[str, Any]]:
        found = await self.call("GET", "/machines")
        return found if isinstance(found, list) else []

    async def create_machine(
        self, name: str, volume_id: str | None, env: dict[str, str], size: Size | None = None
    ) -> str:
        """A machine running the hosted image, behind Fly's proxy on 443 and 80 (the service is what the proxy
        routes to, and what starts a stopped machine on a request and stops an idle one). A runtime's has its size
        and its volume, and stops when idle; the doorman's (no size) is the smallest, has no volume and never stops."""
        s = self.settings
        always_on = size is None
        guest = SIZES["small"] if size is None else size
        service = {
            "protocol": "tcp",
            "internal_port": 7777,
            "autostart": True,
            "autostop": "off" if always_on else "stop",
            "ports": [{"port": 443, "handlers": ["tls", "http"]}, {"port": 80, "handlers": ["http"]}],
        }
        config: dict[str, Any] = {
            "image": s.fly_image,
            "env": env,
            "guest": {
                "cpu_kind": guest.cpu_kind,
                "cpus": guest.cpus,
                "memory_mb": 256 if always_on else guest.memory_mb,
            },
            "services": [service],
            "restart": {"policy": "always" if always_on else "on-failure"},
            "auto_destroy": False,
        }
        if volume_id is not None:
            config["mounts"] = [{"volume": volume_id, "path": "/data"}]
        made = await self.call(
            "POST", "/machines", {"name": name, "region": s.fly_region, "config": config, "skip_launch": True}
        )
        return str(made["id"])

    async def start(self, machine_id: str) -> None:
        await self.call("POST", f"/machines/{machine_id}/start")

    async def restart(self, machine_id: str) -> None:
        await self.call("POST", f"/machines/{machine_id}/restart")

    async def stop(self, machine_id: str) -> None:
        await self.call("POST", f"/machines/{machine_id}/stop")

    async def state(self, machine_id: str) -> str:
        return str((await self.call("GET", f"/machines/{machine_id}")).get("state", ""))

    async def destroy(self, machine_id: str, volume_id: str | None) -> None:
        await self.call("DELETE", f"/machines/{machine_id}?force=true")
        if volume_id:
            await self.call("DELETE", f"/volumes/{volume_id}")
