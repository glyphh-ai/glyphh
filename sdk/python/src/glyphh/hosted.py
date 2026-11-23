"""Your org's hosted Glyphh bots, from your own code: the bots Glyphh runs for you (in its cloud, or on one of your
rrotors), over the Glyphh API at https://api.glyphh.ai with the same API key Ada takes. List and search them, run one
on an input and wait for it, answer what a run asks (a gate unsure, an approval), cancel it, say a gate called it
wrong, read the approvals queue, and install a bot from the templates Glyphh ships.

    bots = HostedBots()                              # GLYPHH_API_KEY (or `glyphh login`'s key); https://api.glyphh.ai
    run = bots.run("inbox-cat", "lunch on Friday?", wait=True)
    if run.waiting:                                  # it asks the person: run.question
        run = bots.answer(run, "yes", wait=True)
    print(run.status, run.output)

(Bots you run on this machine with `glyphh bot` are glyphh.bots: these are the ones Glyphh hosts.)"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional, Union

from . import client
from .client import RETRY_DEADLINE, Ada, Transport, _quote
from .errors import AdaTimeoutError

#: Where the Glyphh API answers. GLYPHH_API_URL moves it, e.g. to a local server under test.
DEFAULT_API_URL = "https://api.glyphh.ai"
#: A run still going: queued, running, or dispatched to its rrotor. Any other status has stopped: `needs_input` waits
#: on the person; `done`, `failed` and `skipped` have ended.
GOING = ("queued", "running", "dispatched")
ENDED = ("done", "failed", "skipped")
#: How long, in seconds, waiting for a run lasts before it raises (the run goes on; wait for it again by its id).
RUN_TIMEOUT = 1800.0
#: The longest pause, in seconds, between two looks at a run.
RUN_POLL = 2.0

Answer = Union[str, List[str], Mapping[str, str]]


class BotInfo(Dict[str, Any]):
    """A bot as the API answers it (`GET /v1/bots/{slug}`): its slug, name, summary, instructions, standing task,
    what it decides (`spec.gates`), connections, schedule, where it runs (`runs_on`: one of the org's rrotors, None
    for Glyphh's cloud) and its `last_run`. A hosted bot is a Claude agent you talk to: `run` it with what you would
    say to it; with nothing, it does its standing task."""

    @property
    def slug(self) -> str:
        return str(self["slug"])

    @property
    def name(self) -> str:
        return str(self.get("name", ""))

    @property
    def summary(self) -> str:
        return str(self.get("summary", ""))


class BotTemplate(Dict[str, Any]):
    """A bot template Glyphh ships (`GET /v1/bot-templates/{slug}`): what it does, the apps it needs connected
    (`apps`), what it decides (`decides`), things to say to it (`examples`) and where it can run (`runs_on`)."""

    @property
    def slug(self) -> str:
        return str(self["slug"])

    @property
    def apps(self) -> List[str]:
        """The apps it needs, by their slug (gmail, slack). The server answers each as `{app, name, tools}`; one from
        before hosted bots were agents answers the slugs alone."""
        return [str(a.get("app", "")) if isinstance(a, Mapping) else str(a) for a in self.get("apps") or []]

    @property
    def runs_on(self) -> List[str]:
        """Where it can run: `cloud`, `rrotor`, or only `rrotor`; both for a server that does not say."""
        return [str(p) for p in self.get("runs_on") or ["cloud", "rrotor"]]


class BotRun(Dict[str, Any]):
    """One run of a bot (`GET /v1/bot-runs/{id}`): its `status` (queued, running, dispatched, needs_input, done,
    failed, skipped), `output`, `error`, `log`, `data` and, while it waits on the person, its `question`
    ({question, options, batch, answer_with, and from servers that say so, step and approval})."""

    @property
    def id(self) -> str:
        return str(self["id"])

    @property
    def status(self) -> str:
        return str(self["status"])

    @property
    def bot(self) -> str:
        return str(self.get("bot_slug", ""))

    @property
    def output(self) -> str:
        return str(self.get("output") or "")

    @property
    def error(self) -> str:
        return str(self.get("error") or "")

    @property
    def question(self) -> Optional[Dict[str, Any]]:
        return self.get("question") or None

    @property
    def going(self) -> bool:
        return self.status in GOING

    @property
    def waiting(self) -> bool:
        """It waits on the person: answer it (`HostedBots.answer`) or cancel it."""
        return self.status == "needs_input"

    @property
    def approval(self) -> bool:
        """It waits on a yes or a no before a step acts."""
        return bool((self.question or {}).get("approval"))

    @property
    def ended(self) -> bool:
        return self.status in ENDED


def _run_id(run: Union[BotRun, str]) -> str:
    return run if isinstance(run, str) else run.id


class HostedBots:
    """Your org's hosted bots, for one API key (the one Ada takes: GLYPHH_API_KEY, or `glyphh login`'s). Reads are
    sent again while the API is unreachable for a moment; a run, an answer, a cancel or an install is sent once."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        *,
        transport: Optional[Transport] = None,
        retry_deadline: float = RETRY_DEADLINE,
    ) -> None:
        found = url or os.environ.get("GLYPHH_API_URL") or DEFAULT_API_URL
        self._api = Ada(found, key, transport=transport, retry_deadline=retry_deadline, read_your_writes=False)
        self.url = self._api.url

    def _get(self, path: str) -> Any:
        return self._api._call("GET", path)

    def _post(self, path: str, body: Optional[Mapping[str, Any]] = None) -> Any:
        return self._api._call("POST", path, dict(body or {}), read=False)

    # bots

    def list(self, q: Optional[str] = None) -> List[BotInfo]:
        """The org's bots by name; with `q`, those whose name, slug or summary has every one of its words."""
        path = "/v1/bots" + (f"?q={_quote(q)}" if q else "")
        return [BotInfo(b) for b in self._get(path)["bots"]]

    def search(self, q: str) -> List[BotInfo]:
        return self.list(q)

    def get(self, slug: str) -> BotInfo:
        return BotInfo(self._get(f"/v1/bots/{_quote(slug)}"))

    def bot(self, slug: str) -> "HostedBot":
        """One bot by its slug, to run and read (no request until it is used)."""
        return HostedBot(self, slug)

    def gates(self, slug: str) -> Dict[str, Any]:
        """What the bot's gates have learned: per gate its precedents, how often it asked, how often it was right."""
        return dict(self._get(f"/v1/bots/{_quote(slug)}/gates")["gates"])

    # runs

    def run(
        self, slug: str, input: str = "", *, wait: bool = False, timeout: float = RUN_TIMEOUT, poll: float = RUN_POLL
    ) -> BotRun:
        """A run of the bot on `input` (`$input` to its steps), queued in the background; with `wait`, waited for
        until it ends or asks the person. A bot has one live run at a time: ConflictError while one is."""
        made = BotRun(self._post(f"/v1/bots/{_quote(slug)}/runs", {"input": input}))
        return self.wait(made, timeout=timeout, poll=poll) if wait else made

    def runs(self, slug: str) -> List[BotRun]:
        """The bot's runs, the newest first (the last 50)."""
        return [BotRun(r) for r in self._get(f"/v1/bots/{_quote(slug)}/runs")["runs"]]

    def get_run(self, run: Union[BotRun, str]) -> BotRun:
        return BotRun(self._get(f"/v1/bot-runs/{_quote(_run_id(run))}"))

    def wait(
        self,
        run: Union[BotRun, str],
        *,
        timeout: float = RUN_TIMEOUT,
        poll: float = RUN_POLL,
        on_progress: Optional[Any] = None,
    ) -> BotRun:
        """Wait for a run to stop going: it ended (done, failed, skipped) or waits on the person (needs_input).
        `on_progress` gets the run each time it is looked at. Past `timeout` seconds, AdaTimeoutError (it goes on)."""
        current = self.get_run(run) if isinstance(run, str) else run
        deadline, pause = client._now() + timeout, 0.25
        while True:
            if on_progress is not None:
                on_progress(current)
            if not current.going:
                return current
            if client._now() + pause > deadline:
                raise AdaTimeoutError(
                    "E_TIMEOUT",
                    f"Run {current.id} of {current.bot} is still {current.status} after {timeout:g} s; it goes on: "
                    "wait for it again by its id.",
                    0,
                    {"run_id": current.id},
                )
            client._sleep(pause)
            pause = min(poll, pause * 2)
            current = self.get_run(current.id)

    def answer(
        self,
        run: Union[BotRun, str],
        answer: Answer,
        *,
        wait: bool = False,
        timeout: float = RUN_TIMEOUT,
        poll: float = RUN_POLL,
    ) -> BotRun:
        """The run that waits on the person, answered: one of its question's options (an approval: yes or no); for a
        batch, `N=option` for each item (`rest=option`), or a map. It carries on (InvalidError when the answer does
        not fit, the run still waiting); with `wait`, waited for."""
        body = {"answer": dict(answer) if isinstance(answer, Mapping) else answer}
        carried = BotRun(self._post(f"/v1/bot-runs/{_quote(_run_id(run))}/answer", body))
        return self.wait(carried, timeout=timeout, poll=poll) if wait else carried

    def cancel(self, run: Union[BotRun, str]) -> BotRun:
        """The run that waits on the person (or is out on its rrotor), ended: it does not carry on."""
        return BotRun(self._post(f"/v1/bot-runs/{_quote(_run_id(run))}/cancel"))

    def wrong(
        self, run: Union[BotRun, str], outcome: str, *, gate: Optional[str] = None, item: Optional[str] = None
    ) -> Dict[str, Any]:
        """A gate called the run (or one of its items, by its key) wrong: what it should have said, learned as a
        precedent. `gate` names which, when the run passed more than one."""
        body = {k: v for k, v in {"outcome": outcome, "gate": gate, "item": item}.items() if v is not None}
        return dict(self._post(f"/v1/bot-runs/{_quote(_run_id(run))}/wrong", body))

    def approvals(self) -> List[BotRun]:
        """The org's approvals queue, oldest first: every bot run waiting on the person (and every swarm's pull
        request waiting for a merge or a no: `kind` swarm), each with what it asks."""
        return [BotRun(r) for r in self._get("/v1/bot-approvals")["runs"]]

    # the templates Glyphh ships

    def templates(self, q: Optional[str] = None) -> List[BotTemplate]:
        path = "/v1/bot-templates" + (f"?q={_quote(q)}" if q else "")
        return [BotTemplate(t) for t in self._get(path)["templates"]]

    def template(self, slug: str) -> BotTemplate:
        return BotTemplate(self._get(f"/v1/bot-templates/{_quote(slug)}"))

    def install(self, slug: str, *, name: Optional[str] = None) -> BotInfo:
        """The org's own bot copied from the template, scoped to its connection of each app the bot needs
        (InvalidError, reason `connections`, naming the apps to connect first). `name`: its name in the org."""
        body = {"name": name} if name else {}
        return BotInfo(self._post(f"/v1/bot-templates/{_quote(slug)}/install", body))


class HostedBot:
    """One of the org's hosted bots by its slug (`HostedBots.bot`)."""

    def __init__(self, bots: HostedBots, slug: str) -> None:
        self.bots, self.slug = bots, slug

    def info(self) -> BotInfo:
        return self.bots.get(self.slug)

    def run(self, input: str = "", *, wait: bool = False, timeout: float = RUN_TIMEOUT, poll: float = RUN_POLL) -> BotRun:
        return self.bots.run(self.slug, input, wait=wait, timeout=timeout, poll=poll)

    def runs(self) -> List[BotRun]:
        return self.bots.runs(self.slug)

    def gates(self) -> Dict[str, Any]:
        return self.bots.gates(self.slug)
