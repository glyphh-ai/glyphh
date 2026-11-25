"""The Resume Screener's steps, one command each, for when Ada is asked through the Glyphh connector's tools. Each
step keeps what it read in the work folder you name and prints what to ask Ada next, as JSON.

    python screen.py read --work DIR --eml application.eml [--role "Backend Engineer"] [--greenhouse record.json]
    python screen.py read --work DIR --email email.txt --file resume.pdf --file cover_letter.docx
        prints {"asks": [{"part", "model", "data", "top"}]}: call ada_facts once for each
        (or {"refused": {...}}: the sender checks refused the message; stop and say why)
    python screen.py compare --work DIR --facts facts.json
        facts.json is {"<part>": <what ada_facts answered for that part>}
        prints {"found": {...}, "cases": {"<signal>": {"model", "data"}}}: call ada_decide once for each
    python screen.py verdict --work DIR --answers answers.json [--told files=fine]
        answers.json is {"<signal>": <what ada_decide answered>}
        prints the verdict, and "keep": what to record in the others model so the next application is compared
        with this one (ada_record)

The work folder holds the application's text until you delete it; delete it when the screening is done."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from screener import mail, steps


def _json(path: str) -> Any:
    return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text())


def read(args: argparse.Namespace) -> dict[str, Any]:
    if args.eml:
        got = mail.read(Path(args.eml).read_bytes())
        got.files += [(Path(f).name, k, d) for f in args.file if (k := mail.kind_of(f, d := Path(f).read_bytes()))]
    else:
        words = Path(args.email).read_text(errors="replace") if args.email else ""
        got = mail.pasted(words, [(Path(f).name, Path(f).read_bytes()) for f in args.file])
    made = steps.read(got, args.role or "", datetime.now(UTC))
    if "refused" in made:
        return made
    made["greenhouse"] = _json(args.greenhouse) if args.greenhouse else None
    (Path(args.work) / "read.json").write_text(json.dumps(made))
    return {"asks": [a | {"model": steps.PREFIX + "others"} for a in steps.asks(made)]}


def compare(args: argparse.Namespace) -> dict[str, Any]:
    made = json.loads((Path(args.work) / "read.json").read_text())
    app = steps.compare(made, _json(args.facts), made.get("greenhouse"))
    (Path(args.work) / "app.json").write_text(json.dumps(app))
    cases = {name: {"model": steps.PREFIX + name, "data": case} for name, case in steps.cases(app).items()}
    return {"found": app["found"], "cases": cases}


def verdict(args: argparse.Namespace) -> dict[str, Any]:
    work = Path(args.work)
    app, made = json.loads((work / "app.json").read_text()), json.loads((work / "read.json").read_text())
    told = dict(t.split("=", 1) for t in args.told)
    out = steps.verdict(app, _json(args.answers), told)
    cases = steps.cases(app)
    for line in out["person"]["signals"]:  # how the person's answer to a signal Ada was unsure of is recorded
        if line["says"] == "unsure" and line["signal"] in cases:
            record = {"name": steps.PREFIX + line["signal"], "data": cases[line["signal"]]}
            line["teach"] = {"tool": "ada_record", "args": record}
    return out | {"keep": {"model": steps.PREFIX + "others", "data": made["others"], "outcome": "alone"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    step = parser.add_subparsers(dest="step", required=True)
    one = step.add_parser("read")
    one.add_argument("--eml", help="the whole message, as an .eml file")
    one.add_argument("--email", help="the email's words (with its headers above them, when you have them)")
    one.add_argument("--file", action="append", default=[], help="the resume or the cover letter (PDF or DOCX)")
    one.add_argument("--role", help="the role applied for, when the subject does not say")
    one.add_argument("--greenhouse", help="the candidate's Greenhouse record: {candidate, application} as JSON")
    two = step.add_parser("compare")
    two.add_argument("--facts", required=True, help="Ada's answers to the asks, by part (a file, or - for stdin)")
    three = step.add_parser("verdict")
    three.add_argument("--answers", required=True, help="Ada's answers to the cases, by signal (a file, or -)")
    three.add_argument("--told", action="append", default=[], help="what the person answered: signal=fine|suspect")
    for sub in (one, two, three):
        sub.add_argument("--work", required=True, help="a folder for this one application's state")
    args = parser.parse_args()
    Path(args.work).mkdir(parents=True, exist_ok=True)
    print(json.dumps({"read": read, "compare": compare, "verdict": verdict}[args.step](args), indent=1))


if __name__ == "__main__":
    main()
