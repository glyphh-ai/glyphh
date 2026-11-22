"""A project's repo through GitHub's REST API, with a turn's GitHub token (docs/specs/bots.md, 10): what a turn on
Glyphh cloud has in place of a checkout. Read: a branch's head, its tree, a file. Write: a branch made, one commit of
a turn's changes on it (git's data API: a tree on the base's, a commit, the branch moved), a pull request opened,
merged or closed, a branch deleted. No code is run and nothing is cloned. A failure is Unavailable, saying what GitHub
said."""

import base64
from typing import Any
from urllib.parse import quote

import httpx

from glyphh_server.errors import Unavailable

API: str = "https://api.github.com"
FILE_MAX: int = 400_000  # a file read or written, in bytes
TREE_MAX: int = 5_000  # paths listed


class Repo:
    def __init__(self, http: httpx.AsyncClient, token: str, repo: str) -> None:
        self.http, self.repo = http, repo
        self.headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28",
        }

    async def _ask(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        try:
            res = await self.http.request(
                method, f"{API}/repos/{self.repo}{path}", json=body, headers=self.headers, timeout=60
            )
        except httpx.HTTPError as err:
            raise Unavailable("GitHub did not answer: try again.", reason="github") from err
        try:
            return res.status_code, res.json()
        except ValueError:
            return res.status_code, {}

    async def _must(self, what: str, method: str, path: str, body: Any = None, ok: tuple[int, ...] = (200, 201)) -> Any:
        status, said = await self._ask(method, path, body)
        if status not in ok:
            why = said.get("message", "") if isinstance(said, dict) else ""
            raise Unavailable(f"GitHub did not {what} ({status}): {why}".strip(": "), reason="github", status=status)
        return said

    async def head(self, branch: str) -> str:
        """The commit the branch is at."""
        said = await self._must(f"find the branch {branch}", "GET", f"/git/ref/heads/{quote(branch)}")
        return str(said["object"]["sha"])

    async def tree(self, sha: str) -> list[str]:
        """Every file's path at that commit (the first TREE_MAX)."""
        said = await self._must("list the repo's files", "GET", f"/git/trees/{sha}?recursive=1")
        return sorted(t["path"] for t in said.get("tree", []) if t.get("type") == "blob")[:TREE_MAX]

    async def read(self, path: str, ref: str) -> str | None:
        """The file's text at that commit; None when it is not there. A file too big, or not text, is refused."""
        status, said = await self._ask("GET", f"/contents/{quote(path)}?ref={ref}")
        if status == 404:
            return None
        if status != 200 or not isinstance(said, dict) or said.get("encoding") != "base64":
            raise Unavailable(f"GitHub did not give {path} ({status}): it is a folder, or too big.", reason="github")
        try:
            return base64.b64decode(said["content"]).decode()
        except ValueError as err:
            raise Unavailable(f"{path} is not text.", reason="github") from err

    async def branch(self, name: str, sha: str) -> None:
        await self._must(f"make the branch {name}", "POST", "/git/refs", {"ref": f"refs/heads/{name}", "sha": sha})

    async def commit(self, branch: str, parent: str, changes: dict[str, str | None], message: str, by: str) -> str:
        """One commit on `branch` (at `parent`) of the changes (a path's new text, or None: deleted), as the bot."""
        entries = [
            {"path": path, "mode": "100644", "type": "blob", **({"sha": None} if text is None else {"content": text})}
            for path, text in sorted(changes.items())
        ]
        tree = await self._must("write the files", "POST", "/git/trees", {"base_tree": parent, "tree": entries})
        author = {"name": by, "email": "bots@glyphh.ai"}
        made = {"message": message, "tree": tree["sha"], "parents": [parent], "author": author}
        commit = await self._must("commit the changes", "POST", "/git/commits", made)
        await self._must("move the branch", "PATCH", f"/git/refs/heads/{quote(branch)}", {"sha": commit["sha"]})
        return str(commit["sha"])

    async def open(self, head: str, base: str, title: str, body: str) -> dict[str, Any]:
        made = {"title": title, "head": head, "base": base, "body": body}
        said = await self._must("open the pull request", "POST", "/pulls", made)
        return {"url": said["html_url"], "number": said["number"]}

    async def merge(self, number: int, title: str) -> tuple[bool, str]:
        """(True, the merge commit) or (False, why it did not merge: a conflict, or a head that moved)."""
        status, said = await self._ask(
            "PUT", f"/pulls/{number}/merge", {"merge_method": "merge", "commit_title": title}
        )
        said = said if isinstance(said, dict) else {}
        if status == 200 and said.get("merged"):
            return True, str(said.get("sha") or "")
        if status in (405, 409, 422):
            return False, str(said.get("message") or "not mergeable")
        raise Unavailable(f"GitHub did not merge the pull request ({status}): {said.get('message', '')}".strip(": "))

    async def close(self, number: int) -> None:
        await self._must("close the pull request", "PATCH", f"/pulls/{number}", {"state": "closed"})

    async def drop(self, branch: str) -> None:
        await self._ask("DELETE", f"/git/refs/heads/{quote(branch)}")  # gone already is fine
