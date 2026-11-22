"""A bot run by a host away from its home: on rrotor (its built-in program glyphh-bot) or in Glyphh's cloud. The host
holds the bot's package and its state; a go writes them into a folder of its own, runs the SDK's runner once (a run
from its first step, or a waiting run carried on with the person's answer) and gives back what the run left, as a
`RunResult` with its `state`, `tokens` and `output` (`RunResult.to_result` is the same as rrotor's `Result`).

A remote bot runs no code of its own: its program is the host's. `HttpProgram` is one that calls each of the bot's
tools (its connections' actions, and `fetch`) over HTTPS at the host that owns them:

    POST <url>   Authorization: Bearer <token>
    {"tool": "<name>", "input": <the step's input>, "run_id": "<the runner's run id>"}
    -> 200 {"result": <any JSON>}       the step's data
    -> 200 {"error": "<why>"}           the step fails, saying why (4xx and 5xx with {"error": ...} too)

    from glyphh import Ada
    from glyphh.bots import ApiClaude
    from glyphh.bots.remote import HttpProgram, go

    left = go(package, ada=Ada(base, key), claude=ApiClaude(api_key=k),
              program=HttpProgram(tool_url, tool_token), state=state, given=given)
    left.to_result()   # {status, data, step, prompt}, data.state the state to keep for the next go
"""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from .. import __version__
from .package import Bot, BotError
from .runner import Runner, RunResult

#: The runner's state in a bot's folder, carried by the host between goes.
STATE = "runs.sqlite"
#: Where the runner keeps that its gate and memory models were made, for each shape of its gates and seed.
INSTALLED = "_glyphh_installed"
#: How long a tool's call may take (the server gives its own 120 seconds).
TOOL_SECONDS = 130.0
#: The longest output a go gives back, in characters.
OUTPUT_MAX = 50_000

Post = Callable[[urllib.request.Request, float], Any]


class ToolError(Exception):
    """A tool's call the host answered with an error (or could not answer): the step that ran it fails."""


def _post(req: urllib.request.Request, timeout: float) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310  the host's own tool URL
            return json.load(res)
    except urllib.error.HTTPError as e:
        try:
            said = json.load(e)
        except ValueError:
            said = None
        if isinstance(said, Mapping) and said.get("error"):
            return said
        raise ToolError(f"the host answered {e.code} {e.reason}") from None
    except urllib.error.URLError as e:
        raise ToolError(f"the host could not be reached: {e.reason}") from None


def _said(error: Any) -> str:
    if isinstance(error, Mapping):
        return str(error.get("message") or error.get("reason") or json.dumps(error, default=str))
    return str(error)


class HttpProgram:
    """A bot's program whose functions are its host's tools: each call POSTs `{tool, input, run_id}` to `url` with the
    bearer `token`, and its `result` is the step's data (an `error` fails the step). `tools` names the tools there
    are (None: any name bot.json gives, the host refusing one it does not have); `post` is how a request is sent
    (urllib; a fake in tests)."""

    def __init__(
        self, url: str, token: str, *, tools: Optional[Iterable[str]] = None, timeout: float = TOOL_SECONDS,
        post: Optional[Post] = None,
    ) -> None:
        if not url.startswith(("https://", "http://")):
            raise BotError(f"a tool URL is http(s)://..., not {url!r}")
        self.url, self._token, self.timeout = url, token, timeout
        self.tools = None if tools is None else frozenset(tools)
        self._send: Post = post or _post

    def __repr__(self) -> str:
        return f"HttpProgram({self.url!r})"  # never the token

    def __getattr__(self, name: str) -> Any:
        tools = self.__dict__.get("tools")
        if name.startswith("_") or (tools is not None and name not in tools):
            raise AttributeError(name)

        def tool(ctx: Any, *given: Any) -> Any:
            # a run step or a gate's case gives one input; a ladder's try and check give several, sent as a list
            sent = given[0] if len(given) == 1 else (list(given) if given else None)
            return self.call(name, sent, getattr(ctx, "run_id", None))

        tool.__name__ = name
        return tool

    def call(self, name: str, given: Any = None, run_id: Optional[str] = None) -> Any:
        """One tool's call at the host: its result, or ToolError with what the host said."""
        body = json.dumps({"tool": name, "input": given, "run_id": run_id}, default=str).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self._token}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": f"glyphh-bot/{__version__}",
        })
        got = self._send(req, self.timeout)
        if not isinstance(got, Mapping):
            raise ToolError(f"{name}: the host's answer is not a JSON object")
        if got.get("error"):
            raise ToolError(f"{name}: {_said(got['error'])}")
        if "result" not in got:
            raise ToolError(f"{name}: the host's answer has no result")
        return got["result"]


def write_package(folder: Path, files: Mapping[str, Any], state: Optional[str] = None) -> Path:
    """A bot's package in `folder` (made): `files` by their path in it (bot.json as an object or its text, agent.md,
    skills/<name>/SKILL.md), and its runner's `state` (base64) when there is one. A remote bot carries no code: a
    path that leaves the folder, or a .py file, is refused."""
    folder.mkdir(parents=True, exist_ok=True)
    if not isinstance(files, Mapping) or "bot.json" not in files:
        raise BotError("a bot's package is its files by path, bot.json among them")
    for path, text in files.items():
        rel = PurePosixPath(str(path))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts or str(rel) == STATE:
            raise BotError(f"{path!r} is not a path inside the bot's folder")
        if rel.suffix == ".py":
            raise BotError(f"{path}: a bot run by a host carries no code, its program is the host's")
        if isinstance(text, (dict, list)) and str(rel) == "bot.json":
            text = json.dumps(text)
        if not isinstance(text, str):
            raise BotError(f"{path}: a file of the package is text")
        out = folder.joinpath(*rel.parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, "utf-8")
    if state:
        try:
            (folder / STATE).write_bytes(base64.b64decode(state, validate=True))
        except ValueError:
            raise BotError("the bot's state is not base64") from None
    return folder


def pack_state(folder: Path) -> Optional[str]:
    """The runner's state in `folder` (its runs.sqlite), base64; None when it has none yet."""
    found = folder / STATE
    return base64.b64encode(found.read_bytes()).decode() if found.exists() else None


def output_of(bot: Bot, result: RunResult) -> str:
    """The run's answer as text: the data of the last of its loop's steps that has any."""
    for step in reversed(bot.loop):
        value = result.data.get(step.get("id")) if isinstance(step, Mapping) else None
        if value is not None:
            text = value if isinstance(value, str) else json.dumps(value, default=str)
            return text[:OUTPUT_MAX]
    return ""


def installed(runner: Runner) -> None:
    """The bot's gate and memory models made and its seed lines kept, once for each shape of its gates and seed (the
    runner's install keeps the seed lines again each time it is called)."""
    spec = runner.bot.spec
    shape = hashlib.sha256(json.dumps([spec.get("gates"), spec.get("seed")], sort_keys=True).encode()).hexdigest()
    if runner.store.state(INSTALLED) != shape:
        runner.install()
        runner.store.set_state(INSTALLED, shape)


def go(
    files: Mapping[str, Any],
    *,
    ada: Any,
    claude: Any,
    program: Any,
    state: Optional[str] = None,
    given: Any = None,
    answer: Any = None,
    runner_options: Optional[Dict[str, Any]] = None,
) -> RunResult:
    """One go of a remote bot: a run from its first step (`given` what it works on), or, with `answer`, the run that
    waits for the person carried on. Its package and `state` are opened in a folder of its own for the go; what it
    leaves is the RunResult, with `state`, `tokens` and `output`. Nobody is at a terminal: a question stops the run,
    `needs_input`. A package that does not load raises BotError."""
    with tempfile.TemporaryDirectory(prefix="glyphh-bot-") as d:
        spec = files.get("bot.json") if isinstance(files, Mapping) else None
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except ValueError:
                raise BotError("bot.json is not JSON") from None
        slug = str(spec.get("slug") or "bot") if isinstance(spec, Mapping) else "bot"
        folder = write_package(Path(d) / slug, files, state)
        bot = Bot.load(folder, program=program)
        options = {"notify": lambda title, text: None, **(runner_options or {})}
        runner = Runner(bot, ada, claude=claude, ask=None, **options)
        installed(runner)
        result = runner.run(given=given) if answer is None else runner.resume(answer)
        result.state = pack_state(folder)
        result.tokens = dict(runner.tokens)
        result.output = output_of(bot, result) if result.status == "done" else None
        return result
