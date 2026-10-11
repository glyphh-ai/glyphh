"""Google and GitHub: where to send the member to sign in, and what they tell us back about them."""

from typing import Protocol

import httpx

from glyphh_server.config import Settings
from glyphh_server.errors import NotFound
from glyphh_server.ops.auth.providers import github, google
from glyphh_server.ops.auth.signin import ProviderProfile


class Provider(Protocol):
    NAME: str

    def configured(self, cfg: Settings) -> bool: ...
    def authorize_url(self, cfg: Settings, redirect_uri: str, state: str) -> str: ...
    async def profile(
        self, http: httpx.AsyncClient, cfg: Settings, code: str, redirect_uri: str
    ) -> ProviderProfile: ...


PROVIDERS: dict[str, Provider] = {"google": google, "github": github}  # type: ignore[dict-item]


def provider(name: str, cfg: Settings) -> Provider:
    found = PROVIDERS.get(name)
    if found is None or not found.configured(cfg):
        raise NotFound("Glyphh doesn't sign in with that provider.", provider=name)
    return found


def available(cfg: Settings) -> list[str]:
    return [name for name, p in PROVIDERS.items() if p.configured(cfg)]
