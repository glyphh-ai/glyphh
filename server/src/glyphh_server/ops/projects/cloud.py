"""A project's step on Glyphh cloud (docs/specs/bots.md, 10). No code runs in the cloud: there is no shell, no checkout
and no browser, so a bot's turn here is its Claude step with the repo as tools, through GitHub's API with the turn's
token (ops/projects/repo.py): list_files, read_file, write_file, delete_file. What it wrote is held until the turn
ends, then committed once on the turn's branch as the bot and opened as a pull request; a turn that changed nothing
opens none. The orchestrator's pick has the two reading tools only. Each answers as rrotor's glyphh_swarm does
(`turn`, `pick`), so the run goes on the same way wherever it runs."""

import difflib
from collections.abc import Awaitable, Callable
from typing import Any

from glyphh_server.errors import GlyphhError
from glyphh_server.ops.projects import turns
from glyphh_server.ops.projects.claude import converse
from glyphh_server.ops.projects.repo import FILE_MAX
from glyphh_server.ops.projects.views import PATH

FILES_MAX: int = 60  # files one turn may change
LISTED: int = 2_000
_PATH = {"path": {"type": "string", "description": "The file's path from the repo's root"}}
_UNDER = {"under": {"type": "string", "description": "Only the files under this folder; none: every file"}}
_TEXT = {"content": {"type": "string", "description": "The file's whole new text"}}


def _tool(name: str, about: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": about,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


READ: list[dict[str, Any]] = [
    _tool("list_files", "The paths of the repo's files.", _UNDER, []),
    _tool("read_file", "A file's text.", _PATH, ["path"]),
]
WRITE: list[dict[str, Any]] = [
    *READ,
    _tool("write_file", "Make or replace a file: give its whole new text.", _PATH | _TEXT, ["path", "content"]),
    _tool("delete_file", "Delete a file.", _PATH, ["path"]),
]


def counted(before: str | None, after: str | None) -> tuple[int, int]:
    """Lines added and removed between a file's two texts."""
    a, b = (before or "").splitlines(), (after or "").splitlines()
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    added = sum(j2 - j1 for tag, _, _, j1, j2 in ops if tag in ("replace", "insert"))
    return added, sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag in ("replace", "delete"))


class Work:
    """One step's view of the repo at the commit it began from: what it reads, and what it has written so far."""

    def __init__(self, repo: Any, sha: str, tools: list[dict[str, Any]]) -> None:
        self.repo, self.sha, self.names = repo, sha, {t["name"] for t in tools}
        self.changes: dict[str, str | None] = {}

    async def text(self, path: str) -> str | None:
        return self.changes[path] if path in self.changes else await self.repo.read(path, self.sha)

    async def call(self, name: str, given: dict[str, Any]) -> str:
        """A tool run; what went wrong is said to Claude in words, so it can go on."""
        try:
            if name not in self.names:
                return f"Error: there is no tool {name} here."
            return await getattr(self, f"_{name}")(given)
        except GlyphhError as err:
            return f"Error: {err.message}"

    def _path(self, given: dict[str, Any]) -> str:
        path = str(given.get("path") or "")
        if not PATH.fullmatch(path) or path.startswith(".git/"):
            raise GlyphhError(f"{path!r} is not a file's path from the repo's root.")
        return path

    async def _list_files(self, given: dict[str, Any]) -> str:
        under = str(given.get("under") or "").strip("/")
        paths = (set(await self.repo.tree(self.sha)) | set(self.changes)) - {
            p for p, t in self.changes.items() if t is None
        }
        found = sorted(p for p in paths if not under or p.startswith(under + "/"))
        more = f"\n(and {len(found) - LISTED} more: list a folder)" if len(found) > LISTED else ""
        return "\n".join(found[:LISTED]) + more or "(no files)"

    async def _read_file(self, given: dict[str, Any]) -> str:
        text = await self.text(self._path(given))
        return "There is no such file." if text is None else text

    async def _write_file(self, given: dict[str, Any]) -> str:
        path, text = self._path(given), str(given.get("content") or "")
        if len(text.encode()) > FILE_MAX:
            raise GlyphhError(f"A file here is at most {FILE_MAX // 1000} kB.")
        if path not in self.changes and len(self.changes) >= FILES_MAX:
            raise GlyphhError(f"A turn on Glyphh cloud changes at most {FILES_MAX} files.")
        self.changes[path] = text
        return f"Wrote {path}."

    async def _delete_file(self, given: dict[str, Any]) -> str:
        path = self._path(given)
        if await self.text(path) is None:
            return "There is no such file."
        self.changes[path] = None
        return f"Deleted {path}."

    async def changed(self) -> tuple[dict[str, str | None], list[dict[str, Any]]]:
        """What the step really changed (a file written back as it was is no change), and each file's lines."""
        kept: dict[str, str | None] = {}
        files = []
        for path, text in sorted(self.changes.items()):
            before = await self.repo.read(path, self.sha)
            if before != text:
                added, removed = counted(before, text)
                kept[path] = text
                files.append({"path": path, "added": added, "removed": removed})
        return kept, files


async def _asked(svc: Any, run: Any, inputs: dict[str, Any], tools: list[dict[str, Any]]) -> tuple[Any, Any, Any]:
    repo = await svc.repo_of(run)
    work = Work(repo, await repo.head(inputs["base"]), tools)
    claude, metered = await svc.claude_of(run.org_id, inputs["model"])
    said = await converse(claude, metered, (inputs["persona"], inputs["prompt"]), tools, work.call, run.effort)
    return repo, work, said


def _usage(said: Any) -> dict[str, int]:
    return {"input_tokens": said.input_tokens, "output_tokens": said.output_tokens}


async def turn(svc: Any, run: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """A bot's turn: its Claude step with the repo's files as tools, then its changes committed and opened as a pull
    request (none when it changed nothing)."""
    repo, work, said = await _asked(svc, run, inputs, WRITE)
    branch, n = str(inputs["branch"]), int(str(inputs["branch"]).split("-")[1])
    title = turns.title(inputs["bot_name"], said.text, n)
    out = {"said": said.text, "title": title, "usage": _usage(said), "done": turns.is_done(said.text)}
    changes, files = await work.changed()
    if not changes:
        return {**out, "status": "unchanged", "pr_url": None, "number": None, "head_sha": None, "files": []}
    await repo.branch(branch, work.sha)
    head = await repo.commit(branch, work.sha, changes, title, inputs["bot_name"])
    pr = await repo.open(branch, inputs["base"], title, said.text)
    return {**out, "status": "open", "pr_url": pr["url"], "number": pr["number"], "head_sha": head, "files": files}


async def pick(svc: Any, run: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """The orchestrator's pick: Claude reading the repo, answering who goes next."""
    _, _, said = await _asked(svc, run, inputs, READ)
    return {"status": "picked", "answer": said.text, "usage": _usage(said)}


STEPS: dict[str, Callable[[Any, Any, dict[str, Any]], Awaitable[dict[str, Any]]]] = {"turn": turn, "pick": pick}
