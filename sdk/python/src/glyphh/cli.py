"""`glyphh`: Ada Cloud from a terminal, for people and for agents with a shell. Every command prints the API's own
answer as JSON on stdout; a refusal prints `{"error": {code, message, ...}}` on stderr and exits 1, a usage
mistake exits 2. It signs in as the plugin does (`glyphh login`, the device flow) or runs on GLYPHH_API_KEY.

    glyphh login
    glyphh models
    glyphh create tickets --spec spec.json
    glyphh import tickets history.csv --mapping '{"Plan": "ticket.what.plan", "Result": "outcome"}'
    glyphh decide tickets '{"ticket": {"what": {"plan": "pro", "text": "charged twice"}}}'
    glyphh record tickets @case.json --outcome refund

A JSON argument is the JSON itself, `@file` for a file's, or `-` for stdin's."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, List, Optional, Sequence

from . import __version__
from .client import Ada, AdaVersions, Decision, Job, Usage
from .errors import AdaError
from .signin import SignIn


def _json(text: str) -> Any:
    raw = sys.stdin.read() if text == "-" else Path(text[1:]).read_text("utf-8") if text.startswith("@") else text
    try:
        return json.loads(raw)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"not JSON: {e}") from e


def _lines(path: str) -> List[Any]:
    """A JSON Lines file of cases (`-`: stdin), or one JSON array of them."""
    raw = sys.stdin.read() if path == "-" else Path(path).read_text("utf-8")
    if raw.lstrip().startswith("["):
        return list(json.loads(raw))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _plain(v: Any) -> Any:
    """What to print: the API's own answer where the SDK kept it, else the SDK's object as JSON."""
    if isinstance(v, (Decision, Job, Usage, AdaVersions)):
        return v.data
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return dataclasses.asdict(v)
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def _out(v: Any) -> None:
    print(json.dumps(_plain(v), indent=2, default=str))


def _progress(quiet: bool):
    if quiet:
        return None

    def show(job: Job) -> None:
        print(f"{job.kind} {job.state} {job.percent:g}%", file=sys.stderr)

    return show


# commands: each takes the parsed arguments and prints its answer


def login(a: argparse.Namespace) -> None:
    flow = SignIn()
    who = flow.whoami()
    if who:
        return _out({"signed_in": True, "email": who})
    p = flow.start()
    print(f"Open {p.verification_uri_complete} and approve the code {p.user_code}.", file=sys.stderr)
    if not a.no_browser:
        webbrowser.open(p.verification_uri_complete)
    print("Waiting for the approval...", file=sys.stderr)
    _out({"signed_in": True, "email": flow.wait(p)})


def logout(_: argparse.Namespace) -> None:
    _out({"signed_out": SignIn().sign_out()})


def whoami(_: argparse.Namespace) -> None:
    who = SignIn().whoami()
    _out({"signed_in": bool(who), "email": who})


def models(_: argparse.Namespace) -> None:
    _out(Ada().models())


def model(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).info())


def spec(a: argparse.Namespace) -> None:
    m = Ada().model(a.name)
    _out(m.set_spec(a.set, note=a.note, wait=not a.no_wait, on_progress=_progress(a.quiet)) if a.set else m.spec())


def create(a: argparse.Namespace) -> None:
    _out(Ada().create_model(a.name, a.spec, ada=a.ada).created)


def delete(a: argparse.Namespace) -> None:
    if a.confirm != a.name:
        raise AdaError("E_INVALID", f"Deleting {a.name} drops every precedent it holds: say --confirm {a.name}.")
    _out(Ada().delete_model(a.name))


def record(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).record(a.data, a.outcome, outcomes=a.outcomes))


def record_many(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).record_many(_lines(a.file)))


def grade(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).grade(a.id, a.value, output=a.output))


def forget(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).forget(a.id))


def import_(a: argparse.Namespace) -> None:
    m = Ada().model(a.name)
    job = m.import_file(
        a.file,
        format=a.format,
        mapping=a.mapping,
        partial=a.partial,
        learn=not a.no_learn,
        wait=not a.no_wait,
        on_progress=_progress(a.quiet),
    )
    _out(job)


def learn(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).learn(sample=a.sample, on_progress=_progress(a.quiet)))


def calibrate(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).calibrate())


def decide(a: argparse.Namespace) -> None:
    outputs = a.outputs.split(",") if a.outputs else None
    include = ["facts"] if a.facts else None
    _out(Ada().decide(a.name, a.data, output=a.output, outputs=outputs, include=include, clearance=a.clearance))


def _ask(function: str):
    def run(a: argparse.Namespace) -> None:
        m = Ada().model(a.name)
        extra = {"top": a.top} if function == "facts" and a.top is not None else {}
        _out(getattr(m, function)(a.data, output=a.output, clearance=a.clearance, **extra))

    return run


def backtest(a: argparse.Namespace) -> None:
    m = Ada().model(a.name)
    _out(
        m.backtest(
            a.candidates or (),
            ada=a.ada,
            holdout=a.holdout,
            output=a.output,
            wait=not a.no_wait,
            on_progress=_progress(a.quiet),
        )
    )


def settings(a: argparse.Namespace) -> None:
    m = Ada().model(a.name)
    if a.changes is None:
        return _out(m.settings())
    _out(m.settings(a.changes, note=a.note, backtest=a.backtest, wait=not a.no_wait, on_progress=_progress(a.quiet)))


def versions(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).versions())


def activate(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).activate(a.version))


def upgrade(a: argparse.Namespace) -> None:
    m = Ada().model(a.name)
    _out(m.upgrade(ada=a.ada, note=a.note, backtest=a.backtest, wait=not a.no_wait, on_progress=_progress(a.quiet)))


def export(a: argparse.Namespace) -> None:
    _out(Ada().model(a.name).export(format=a.format, to=a.to, wait=not a.no_wait, on_progress=_progress(a.quiet)))


def job(a: argparse.Namespace) -> None:
    ada = Ada()
    _out(ada.wait(a.id, on_progress=_progress(a.quiet)) if a.wait else ada.job(a.id))


def usage(_: argparse.Namespace) -> None:
    _out(Ada().usage())


def releases(_: argparse.Namespace) -> None:
    _out(Ada().ada.versions())


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="glyphh",
        description="Ada Cloud from a terminal: every answer is JSON on stdout. A JSON argument is the JSON, @file, or -.",
    )
    top.add_argument("--version", action="version", version=f"glyphh {__version__}")
    sub = top.add_subparsers(dest="command", required=True, metavar="command")

    def cmd(name: str, run, about: str, *, model_arg: bool = True, quiet: bool = False) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=about, description=about)
        if model_arg:
            p.add_argument("name", help="the model's name")
        if quiet:
            p.add_argument("--quiet", "-q", action="store_true", help="no job progress on stderr")
            p.add_argument("--no-wait", action="store_true", help="answer the job at once, not waited for")
        p.set_defaults(run=run)
        return p

    def ask(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("data", type=_json, help="the case, as JSON (or @file, -)")
        p.add_argument("--output", help="which of the model's named outputs")
        p.add_argument("--clearance", type=float, help="read with less clearance than the sign-in's or key's")
        return p

    p = cmd("login", login, "Sign this machine in to Glyphh (the device flow, as the plugin's)", model_arg=False)
    p.add_argument("--no-browser", action="store_true", help="print the link, do not open it")
    cmd("logout", logout, "Sign this machine out (the plugin's sign-in too: they share it)", model_arg=False)
    cmd("whoami", whoami, "Who this machine is signed in as", model_arg=False)
    cmd("usage", usage, "What the org uses of Ada Cloud against its plan this month", model_arg=False)
    cmd("releases", releases, "Every Ada version: status, dates, notes, the org's models on it", model_arg=False)

    cmd("models", models, "The org's models", model_arg=False)
    cmd("model", model, "One model: its active version, size, settings and Ada version")
    p = cmd("spec", spec, "A model's spec; with --set, a new version of it", quiet=True)
    p.add_argument("--set", type=_json, help="the new spec, as JSON (or @file, -)")
    p.add_argument("--note", help="why, kept with the version")
    p = cmd("create", create, "Make a model from its JSON spec: version 1, empty")
    p.add_argument("--spec", type=_json, required=True, help="the spec, as JSON (or @file, -)")
    p.add_argument("--ada", help="the Ada version it runs (default: the latest stable)")
    p = cmd("delete", delete, "Delete a model and every precedent it holds; not undone")
    p.add_argument("--confirm", required=True, help="the model's name again")

    p = cmd("record", record, "Record one case, with its outcome when known")
    p.add_argument("data", type=_json, help="the case, as JSON (or @file, -)")
    p.add_argument("--outcome", help="the outcome")
    p.add_argument("--outcomes", type=_json, help="each named output's outcome, as JSON")
    p = cmd("record-many", record_many, "Record many cases: a JSON Lines file of {data, outcome?, outcomes?, ts?}")
    p.add_argument("file", help="the file (- for stdin)")
    p = cmd("grade", grade, "Give a case already in its outcome")
    p.add_argument("id", help="the precedent's id")
    p.add_argument("value", type=_json, help='the outcome, as JSON ("refund", true, 120, ["web"])')
    p.add_argument("--output", help="which named output")
    p = cmd("forget", forget, "Forget one case")
    p.add_argument("id", help="the precedent's id")
    p = cmd("import", import_, "Import a history file (.csv, .jsonl, .sqlite, a model's own .zip) as a job", quiet=True)
    p.add_argument("file", help="the file")
    p.add_argument("--format", help="csv, jsonl or ada_sqlite (default: by the extension)")
    p.add_argument("--mapping", type=_json, help='columns to roles, as JSON: {"Plan": "ticket.what.plan", ...}')
    p.add_argument("--partial", action="store_true", help="keep the rows that fit when some are refused")
    p.add_argument("--no-learn", action="store_true", help="do not learn once it is in")

    p = cmd("learn", learn, "Weigh the roles from the precedents, then calibrate", quiet=True)
    p.add_argument("--sample", type=int, help="learn from this many precedents")
    cmd("calibrate", calibrate, "Calibrate the probabilities alone")

    p = ask(cmd("decide", decide, "Decide a case: outcome, probabilities, expected cost, ask, receipts"))
    p.add_argument("--outputs", help="several named outputs at once, comma separated")
    p.add_argument("--facts", action="store_true", help="add the nearest fact tree")
    ask(cmd("query", _ask("query"), "The nearest precedents' vote"))
    ask(cmd("probabilities", _ask("probabilities"), "P(outcome | case), calibrated"))
    p = ask(cmd("facts", _ask("facts"), "The nearest fact trees, best first"))
    p.add_argument("--top", type=int, help="how many")

    p = cmd("backtest", backtest, "Score the live version and candidates on held-out cases", quiet=True)
    p.add_argument("--candidates", type=_json, help='as JSON: [{"settings": {...}, "name": "..."}]')
    p.add_argument("--holdout", type=_json, help='as JSON: {"newest": 200}')
    p.add_argument("--ada", help="score on another Ada version")
    p.add_argument("--output", help="which named output")
    p = cmd("settings", settings, "Every lever; with --changes, a new version", quiet=True)
    p.add_argument("--changes", type=_json, help='as JSON: {"word_evidence": 0}')
    p.add_argument("--note", help="why, kept with the version")
    p.add_argument("--backtest", help="the backtest job that argues for it")
    cmd("versions", versions, "A model's versions, who made them, why, and the Ada each runs")
    p = cmd("activate", activate, "Make an earlier version live again")
    p.add_argument("version", type=int)
    p = cmd("upgrade", upgrade, "Move a model to another Ada version (default: the latest stable)", quiet=True)
    p.add_argument("--ada", help="the Ada version")
    p.add_argument("--note", help="why, kept with the version")
    p.add_argument("--backtest", help="the backtest job that argues for it")
    p = cmd("export", export, "Everything out, as a file", quiet=True)
    p.add_argument("--format", default="jsonl", help="jsonl (default) or another the API takes")
    p.add_argument("--to", help="where to write the file (default: answer its download link)")

    p = cmd("job", job, "A job's state and progress", model_arg=False)
    p.add_argument("id", help="the job's id")
    p.add_argument("--wait", action="store_true", help="wait for it to end")
    p.add_argument("--quiet", "-q", action="store_true", help="no progress on stderr")
    return top


def main(argv: Optional[Sequence[str]] = None) -> int:
    a = parser().parse_args(argv)
    try:
        a.run(a)
    except AdaError as e:
        err = {"code": e.code, "message": e.message, **{k: v for k, v in (e.detail or {}).items() if k != "job"}}
        print(json.dumps({"error": err}, indent=2, default=str), file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(json.dumps({"error": {"code": "E_LOCAL", "message": str(e)}}, indent=2), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
