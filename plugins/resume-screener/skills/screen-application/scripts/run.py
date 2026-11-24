"""The Resume Screener end to end through the Glyphh SDK (pip install glyphh pypdf), for when the connector's tools
are not there: the same steps in the same order (screener/steps.py), with Ada asked from here. The key is your
own: `glyphh login`, or GLYPHH_API_KEY.

    python run.py --eml application.eml [--role "Backend Engineer"] [--keep]
    python run.py --email email.txt --file resume.pdf --file cover_letter.docx

`--keep` records the application in your `others` model so the next one is compared with it. Without it nothing
is recorded anywhere. `--stdin` reads one JSON request instead ({email, files: [{name, base64}], role}) and never
touches the disk: it is how a web page runs this same code on files held in memory."""

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from screener import mail, steps


def said(decision: Any) -> dict[str, Any]:
    """An SDK decision as the steps read an answer."""
    return {"outcome": decision.outcome, "probabilities": dict(decision.probabilities or {}), "ask": decision.ask}


def screen(ada: Any, got: mail.Mail, role: str = "", signals: dict[str, Any] | None = None, keep: bool = False,
           prefix: str = steps.PREFIX, now: datetime | None = None) -> dict[str, Any]:  # fmt: skip
    """One application, start to verdict. `ada` is the SDK's client (glyphh.Ada)."""
    made = steps.read(got, role, now or datetime.now(UTC))
    if "refused" in made:
        return made
    others = ada.model(prefix + "others")
    facts = {a["part"]: others.facts(a["data"], top=a["top"]).data for a in steps.asks(made)}
    app = steps.compare(made, facts, signals)
    answers = {name: said(ada.model(prefix + name).decide(case)) for name, case in steps.cases(app).items()}
    if keep:
        others.record(made["others"], "alone")
    return steps.verdict(app, answers)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eml")
    parser.add_argument("--email")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--role", default="")
    parser.add_argument("--greenhouse")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--prefix", default=steps.PREFIX, help="what your models' names begin with")
    parser.add_argument("--stdin", action="store_true")
    args = parser.parse_args()
    from glyphh import Ada

    signals = json.loads(Path(args.greenhouse).read_text()) if args.greenhouse else None
    if args.stdin:
        asked = json.loads(sys.stdin.read())
        files = [(str(f["name"]), base64.b64decode(f["base64"])) for f in asked.get("files") or []]
        got, args.role = mail.pasted(str(asked.get("email") or ""), files), str(asked.get("role") or "")
    elif args.eml:
        got = mail.read(Path(args.eml).read_bytes())
    else:
        words = Path(args.email).read_text(errors="replace") if args.email else ""
        got = mail.pasted(words, [(Path(f).name, Path(f).read_bytes()) for f in args.file])
    print(json.dumps(screen(Ada(), got, args.role, signals, args.keep, args.prefix), indent=1))


if __name__ == "__main__":
    main()
