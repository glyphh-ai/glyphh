"""GitHub for the Glyphh GitHub App, faked at the HTTP layer: the App's own calls (each JWT checked against the App's
public key: the installation that covers a repo, an account's login, a token minted) and the calls made with a token
it minted (the repos its installation covers, a repo's branches, who may push), each held to the repo and the
permissions the token was minted with."""

import json
from typing import Any

import httpx

from tests.conftest import GITHUB_APP_ID, GITHUB_APP_KEY
from tests.fakes import FakeGitHubApp

EXPIRES: str = "2026-11-22T13:00:00Z"


class FakeGitHub:
    def __init__(self) -> None:
        self.app = FakeGitHubApp(GITHUB_APP_KEY.public_key(), GITHUB_APP_ID)
        self.installed: dict[str, int] = {}  # a repo (owner/name) -> the installation that covers it
        self.private: set[str] = set()
        self.logins: dict[str, str] = {}  # an account's id -> its login
        self.pushers: dict[str, set[str]] = {}  # a repo -> the logins that may push to it
        self.branches: dict[str, list[str]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}  # a minted token -> its installation, repos and permissions
        self.down: set[str] = set()  # a call (its last path segment) GitHub fails, or "*" for all
        self.asked: list[tuple[str, str]] = []

    def install(self, repo: str, installation_id: int, *pushers: tuple[str, str]) -> None:
        """The App installed on the repo; `pushers`: (account id, login) of those who may push to it."""
        self.installed[repo] = installation_id
        self.branches.setdefault(repo, ["main", "dev"])
        self.logins |= dict(pushers)
        self.pushers[repo] = {login for _, login in pushers}

    def _mint(self, installation_id: int, body: dict[str, Any]) -> httpx.Response:
        covered = sorted(r for r, i in self.installed.items() if i == installation_id)
        if not covered:
            return httpx.Response(404, json={"message": "Not Found"})
        wanted = [r for r in covered if r.split("/")[1] in body["repositories"]] if "repositories" in body else covered
        if not wanted:
            return httpx.Response(422, json={"message": "There is at least one repository that does not exist"})
        token = f"ghs_fake_{len(self.tokens) + 1}"
        self.tokens[token] = {"installation": installation_id, "repos": wanted, "permissions": body["permissions"]}
        return httpx.Response(201, json={"token": token, "expires_at": EXPIRES})

    def _as_app(self, request: httpx.Request, parts: list[str]) -> httpx.Response:
        assert self.app._claims(request)["iss"] == GITHUB_APP_ID
        if parts[0] == "repos":
            found = self.installed.get(f"{parts[1]}/{parts[2]}")
            return httpx.Response(200, json={"id": found}) if found else httpx.Response(404, json={})
        if parts[0] == "user":
            return httpx.Response(200, json={"id": int(parts[1]), "login": self.logins.get(parts[1], "ghost")})
        return self._mint(int(parts[2]), json.loads(request.content))

    def _repo(self, repo: str) -> dict[str, Any]:
        name = {"full_name": repo, "html_url": f"https://github.com/{repo}"}
        return name | {"private": repo in self.private, "default_branch": self.branches[repo][0]}

    def _with_token(self, token: dict[str, Any], parts: list[str], query: dict[str, str]) -> httpx.Response:
        assert "metadata" in token["permissions"]
        if parts[0] == "installation":
            page, size = int(query["page"]), int(query["per_page"])
            listed = [self._repo(r) for r in token["repos"]][(page - 1) * size : page * size]
            return httpx.Response(200, json={"repositories": listed})
        repo = f"{parts[1]}/{parts[2]}"
        assert repo in token["repos"], "a token is for its own repos"
        if len(parts) == 3:
            return httpx.Response(200, json=self._repo(repo))
        if parts[3] == "branches":
            return httpx.Response(200, json=[{"name": b} for b in self.branches[repo]])
        login = parts[4]
        if login not in self.logins.values():
            return httpx.Response(404, json={"message": "Not Found"})
        account = next(i for i, name in self.logins.items() if name == login)
        may = "write" if login in self.pushers[repo] else "read"
        return httpx.Response(200, json={"permission": may, "user": {"id": int(account), "login": login}})

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        parts = request.url.path.strip("/").split("/")
        self.asked.append((request.method, request.url.path))
        if "*" in self.down or parts[-1] in self.down:
            return httpx.Response(502, text="bad gateway")
        bearer = request.headers["authorization"].removeprefix("Bearer ")
        if bearer in self.tokens:
            return self._with_token(self.tokens[bearer], parts, dict(request.url.params))
        return self._as_app(request, parts)

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
