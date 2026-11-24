"""The Resume Screener's fixed order of steps, as plain functions with Ada asked in between by whoever runs them
(Claude through the Glyphh connector's ada_* tools, or run.py through the Glyphh SDK):

1. `read`: the email and its files read, the resume told from the cover letter, the timestamps measured, and the
   application as the `others` model holds it. A message the sender checks refuse stops here, saying why.
2. `asks`: the questions for Ada's `others` model, one per part (ada_facts).
3. `compare`: Ada's nearest applications turned into what was found, then the checks in order (content, files,
   timing, writing).
4. `cases`: the case each model is asked (ada_decide): fit, files, timing, made, and greenhouse when its signals
   were given.
5. `verdict`: is this a real person (each signal, then one answer), the fit second, how it was written last.

The models' specs and how an application maps to each one's case are the JSON files in models/."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import applicants, checks, greenhouse, others, timing
from .mail import Mail

MODELS: Path = Path(__file__).resolve().parent.parent.parent / "models"
PREFIX: str = "screener-"  # a model's name in Ada is this and the model's own name: screener-fit
PERSON: tuple[str, ...] = ("timing", "files", "others", "greenhouse")  # the signals of a real person, in order
TITLES: dict[str, str] = {"timing": "Email timestamps", "files": "The files themselves",
                          "others": "Against the other applications", "greenhouse": "Greenhouse"}  # fmt: skip
NOTED: frozenset[str] = frozenset(("none", "applied_before"))  # flags that are told and never asked about


def models() -> dict[str, dict[str, Any]]:
    """Every model the screener uses, by name: its question, outcomes, case mapping and spec."""
    return {p.stem: json.loads(p.read_text()) for p in sorted(MODELS.glob("*.json"))}


def fill(shape: Any, item: dict[str, Any]) -> Any:
    """A model's case: each `$item.a.b` of its mapping replaced by that value of the application; a value the
    application does not have is left out (what a case leaves out weighs nothing)."""
    if isinstance(shape, dict):
        made = {k: fill(v, item) for k, v in shape.items()}
        return {k: v for k, v in made.items() if v is not None and v != {}}
    if isinstance(shape, str) and shape.startswith("$item."):
        at: Any = item
        for key in shape[6:].split("."):
            at = at.get(key) if isinstance(at, dict) else None
        return at
    return shape


def read(mail: Mail, role: str = "", now: datetime | None = None) -> dict[str, Any]:
    """Step 1. {raw, others}, or {refused: why}. `role` is the role applied for when the person says it (else it
    is read from the subject)."""
    raw, why = applicants.of_mail(mail, raw=True)
    if raw is None:
        return {"refused": why}
    if role.strip():
        raw["role"] = role.strip().lower()
        raw["label"] = f"{raw['name']} - {raw['role']}"
    raw["timing"] = timing.read(mail.date, mail.received, now)
    return {"raw": raw, "others": others.prints(raw)}


def asks(got: dict[str, Any]) -> list[dict[str, Any]]:
    """Step 2. What to ask the `others` model: one {part, data, top} per part the application has."""
    case = got["others"]
    return [{"part": p, "data": {p: case[p]}, "top": others.TOP} for p in others.PARTS if p in case]


def _list(answer: Any) -> list[Any]:
    """Ada's nearest fact trees as a list, whether the answer came bare (the API) or wrapped (a connector tool)."""
    if isinstance(answer, dict):
        return next((v for v in answer.values() if isinstance(v, list)), [])
    return answer if isinstance(answer, list) else []


def compare(got: dict[str, Any], facts: dict[str, Any], signals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Step 3. The application, checked. `facts` is Ada's answer to each of `asks`, by part (a part not asked or
    not answered counts as nothing held). `signals` is the candidate's Greenhouse record, when there is one."""
    near = {part: others.nearest(_list(answer)) for part, answer in facts.items()}
    seen = others.compared(lambda asked: near.get(next(iter(asked)), []), got["others"])
    raw = got["raw"] | {"timing": timing.with_burst(got["raw"]["timing"], seen["together"])}
    app = checks.whole(raw)
    app["others"] = seen
    app["found"]["others"] = seen["found"]
    if signals:
        app["greenhouse"] = greenhouse.read(signals.get("candidate") or {}, signals.get("application") or {})
        app["found"]["greenhouse"] = greenhouse.found(app["greenhouse"])
    return app


def cases(app: dict[str, Any]) -> dict[str, Any]:
    """Step 4. The case of each model that is asked to decide (the `others` model was asked in step 2)."""
    asked = {name: fill(m["case"], app) for name, m in models().items() if name != "others"}
    return {name: case for name, case in asked.items() if name != "greenhouse" or "greenhouse" in app}


def checked(app: dict[str, Any], signal: str) -> bool:
    """Whether there was anything for the signal to check."""
    if signal == "timing":
        return app["timing"]["dated"] == "yes" or app["timing"]["hops"] > 0
    if signal == "files":
        return app["file"]["kind"] not in ("none", "text")
    return signal == "others" or signal in app


def _confidence(answer: dict[str, Any]) -> float | None:
    p = (answer.get("probabilities") or {}).get(answer.get("outcome") or "")
    return round(float(p), 2) if isinstance(p, int | float) else None


def signal(app: dict[str, Any], name: str, answer: dict[str, Any] | None) -> dict[str, Any]:
    """One signal's line of the verdict: what it says (fine, suspect, unsure, not checked), who said it and what
    was found. Ada's answer stands when Ada is sure. When Ada is not sure, a signal that found something is
    `unsure` (the person is asked, and their answer becomes a precedent) and one that found nothing is `fine`.
    The `others` signal is Ada's nearest applications, not a decision: anything it names, other than the same
    person applying again, is `unsure`."""
    out: dict[str, Any] = {"signal": name, "title": TITLES[name], "found": list(app["found"].get(name) or [])}
    if not checked(app, name):
        return out | {"says": "not checked", "by": "rule", "found": ["there was nothing to check"]}
    flags = app["others"]["flags"] if name == "others" else (app.get({"files": "file"}.get(name, name)) or {}).get("flags")
    flagged = bool(set(flags or ["none"]) - NOTED)
    if name == "others":
        return out | {"says": "unsure" if flagged else "fine", "by": "ada", "near": app["others"]["near"]}
    if answer and answer.get("outcome") and not answer.get("ask"):
        return out | {"says": answer["outcome"], "by": "ada", "confidence": _confidence(answer)}
    return out | {"says": "unsure" if flagged else "fine", "by": "rule"}


def verdict(app: dict[str, Any], answers: dict[str, Any], told: dict[str, str] | None = None) -> dict[str, Any]:
    """Step 5. `answers` is Ada's answer to each of `cases`, by model ({outcome, probabilities, ask}). `told` is
    what the person answered when asked about a signal ({signal: fine or suspect}); it stands over everything.
    A real person: no signal says suspect and none is unsure. Suspect: any signal says suspect. Otherwise unsure;
    and unsure when nothing could be checked at all."""
    lines = []
    for name in PERSON:
        if name == "greenhouse" and "greenhouse" not in app:
            continue
        line = signal(app, name, answers.get(name))
        if told and name in told:
            line |= {"says": told[name], "by": "you"}
            line.pop("confidence", None)
        lines.append(line)
    says = [line["says"] for line in lines]
    nothing = all(s == "not checked" for s in says)
    person = "suspect" if "suspect" in says else "unsure" if "unsure" in says or nothing else "real person"
    fit, made = answers.get("fit") or {}, answers.get("made") or {}
    return {
        "applicant": app["label"], "name": app["name"], "role": app["role"], "id": app["id"],
        "person": {"verdict": person, "signals": lines, "ask": [ln["signal"] for ln in lines if ln["says"] == "unsure"]},
        "fit": {"outcome": fit.get("outcome") or "no answer", "confidence": _confidence(fit),
                "ask": bool(fit.get("ask", True)), "found": list(app["found"].get("content") or [])},
        "made": {"outcome": made.get("outcome") or "no answer", "confidence": _confidence(made),
                 "ask": bool(made.get("ask", True)), "found": list(app["found"].get("writing") or [])},
    }  # fmt: skip
