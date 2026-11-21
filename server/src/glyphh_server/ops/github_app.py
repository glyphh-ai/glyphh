"""The Glyphh GitHub App, as the App itself: a JWT signed with its private key (RS256), then GitHub's App API. Fails
closed: anything but a good answer is GitHub being unavailable, and an installation GitHub doesn't know is not found.
Tests fake GitHub at the HTTP layer; nothing here ever runs against a real App in tests."""

import base64
import json
import logging
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from glyphh_server.config import Settings
from glyphh_server.errors import NotFound, Unavailable
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.github_app")

API: str = "https://api.github.com"
# GitHub refuses a JWT that lives over 10 minutes, and allows for clock drift by issuing it a minute early.
JWT_TTL: int = 540
JWT_SKEW: int = 60


def load_key(settings: Settings) -> rsa.RSAPrivateKey | None:
    """The App's private key, checked at start. A PEM whose line breaks were written as \\n is read too."""
    if not settings.github_app_private_key:
        return None
    pem = settings.github_app_private_key.replace("\\n", "\n").encode()
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except ValueError as err:
        raise RuntimeError("GLYPHH_GITHUB_APP_PRIVATE_KEY must be the GitHub App's private key, as PEM.") from err
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RuntimeError("GLYPHH_GITHUB_APP_PRIVATE_KEY must be the GitHub App's private key, as PEM.")
    return key


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def app_jwt(app_id: str, key: rsa.RSAPrivateKey, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {"iat": issued - JWT_SKEW, "exp": issued + JWT_TTL, "iss": app_id}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{body}.{_b64(signature)}"


class GitHubApp:
    def __init__(self, http: httpx.AsyncClient, settings: Settings, key: rsa.RSAPrivateKey | None) -> None:
        if key is None or not settings.github_app_configured:
            raise Unavailable("GitHub isn't set up on this server.", reason="github_off")
        self.http, self.app_id, self.key = http, settings.github_app_id, key

    async def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "authorization": f"Bearer {app_jwt(self.app_id, self.key)}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
        }
        try:
            res = await self.http.request(method, f"{API}{path}", json=body, headers=headers)
            if res.status_code == httpx.codes.NOT_FOUND:
                raise NotFound("GitHub knows no such installation of Glyphh's App.", reason="github_installation")
            res.raise_for_status()
            return res.json()
        except (httpx.HTTPError, ValueError) as err:
            log.warning("github app call failed", extra=fields(path=path, error=repr(err)))
            raise Unavailable("GitHub didn't answer. Try again.", reason="github") from err

    async def installation(self, installation_id: int) -> dict[str, Any]:
        return await self.call("GET", f"/app/installations/{installation_id}")

    async def repo_token(self, installation_id: int, repo_name: str) -> dict[str, Any]:
        """A token for this one repo, read-only on its contents, for one hour."""
        body = {"repositories": [repo_name], "permissions": {"contents": "read"}}
        return await self.call("POST", f"/app/installations/{installation_id}/access_tokens", body)
