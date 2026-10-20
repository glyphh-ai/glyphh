"""Ada on Security Incidents: the Ada product (the ada-private kernel with its English lexicon) in Jev's place in
TypeSafe's workflow — it answers the workflow's questions, and the same policy code decides — by cross-validation.

Code turns each case's state (the alert and the joined records) into typed fields, as a model.py would. For each
of the workflow's questions an Ada model learns, from the other folds' cases, what the references' consensus
answered for cases like it, the way the product is used: record the graded cases, refresh() (learn the role, value
and word weights and the word evidence, then calibrate), decide() each new case. Every case is answered by models
that never saw it: five folds, each answered by models of the other four.

The kernel is Glyphh's and is not published: GLYPHH_KERNEL points at an ada-private checkout (default:
../../ada-private). load_kernel() refuses anything else — an older copy, a kernel without its lexicon, or a lexicon
that does not load — so a run can only ever measure the product.

    uv run python ada.py
"""

from __future__ import annotations

import math
import os
import re
import sys
import time
import tomllib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import run
import score

HERE = Path(__file__).parent
KERNEL = Path(os.environ.get("GLYPHH_KERNEL", HERE.parents[1] / "ada-private")).resolve()
MIN_VERSION = (3, 10, 0)  # the kernel that reads text through the lexicon and learns, calibrates and decides
LEXICON_WORDS, LEXICON_FORMS = 77_817, 192_960  # WordNet 3.0 words, Moby word forms (ada-private/lexicon)
FOLDS = 5


def load_kernel():
    """The ada-private kernel, checked: its version, its lexicon on disk, and the lexicon actually loaded. Exits
    with the reason otherwise; a benchmark of an older or partial kernel is not a benchmark of Ada."""
    need = ["glyphh_kernel.py", "glyphh_spec.py", "glyphh_lexicon.py", "lexicon/words.jsonl.gz", "lexicon/grammar.jsonl.gz", "pyproject.toml"]
    missing = [n for n in need if not (KERNEL / n).is_file()]
    if missing:
        sys.exit(f"{KERNEL} is not an ada-private checkout (missing {', '.join(missing)}); set GLYPHH_KERNEL")
    project = tomllib.loads((KERNEL / "pyproject.toml").read_text())["project"]
    version = tuple(int(p) for p in project["version"].split(".")[:3])
    if version < MIN_VERSION:
        sys.exit(f"{KERNEL} has kernel {project['version']}; Ada is {'.'.join(map(str, MIN_VERSION))} or later")
    sys.path.insert(0, str(KERNEL))
    import glyphh_lexicon
    import glyphh_spec

    words, forms = glyphh_lexicon.LEXICON.size()
    if (words, forms) != (LEXICON_WORDS, LEXICON_FORMS):
        sys.exit(f"the lexicon loaded {words} words and {forms} forms, not {LEXICON_WORDS} and {LEXICON_FORMS}")
    print(f"Ada: kernel {project['version']} from {KERNEL}, lexicon {words:,} words / {forms:,} forms", file=sys.stderr)
    return glyphh_spec


glyphh_spec = load_kernel()

SPEC = {
    "name": "security_incidents",
    "seed": 5,
    "dimension": 4096,
    "layers": [
        {
            "name": "alert",
            "segments": [
                {
                    "name": "what",
                    "roles": [
                        {"name": "detector"},
                        {"name": "title", "text_encoding": "bag_of_words"},
                        {"name": "kinds"},
                        {"name": "indicators", "text_encoding": "bag_of_words", "similarity_weight": 0.6},
                        {"name": "events", "numeric_config": {"min_value": 0, "max_value": 4, "bin_width": 0.5}},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                },
                {
                    # the alert's telemetry as typed fields: defined from TypeSafe's five published example alerts
                    # (process:, file:, registry: lines and the source-event count), not from our cases or misses
                    "name": "evidence",
                    "roles": [
                        {"name": "processes"},
                        {"name": "file_areas"},
                        {"name": "registry_areas"},
                        {"name": "n_process", "numeric_config": {"min_value": 0, "max_value": 6, "bin_width": 1}},
                        {"name": "n_file", "numeric_config": {"min_value": 0, "max_value": 6, "bin_width": 1}},
                        {"name": "n_registry", "numeric_config": {"min_value": 0, "max_value": 4, "bin_width": 1}},
                        {"name": "source_events", "numeric_config": {"min_value": 0, "max_value": 4, "bin_width": 0.5}},
                    ],
                },
            ],
        },
        {
            "name": "context",
            "segments": [
                {
                    "name": "explains",
                    "roles": [
                        {"name": "change"},
                        {"name": "badge"},
                        {"name": "time_off"},
                        {"name": "factor_age", "numeric_config": {"min_value": 0, "max_value": 3, "bin_width": 0.5}},
                    ],
                },
                {
                    "name": "records",
                    "similarity_weight": 0.5,
                    "roles": [{"name": "sources"}, {"name": "notes", "text_encoding": "bag_of_words"}],
                },
            ],
        },
        {
            "name": "asset",
            "similarity_weight": 0.6,
            "segments": [
                {
                    "name": "where",
                    "roles": [
                        {"name": "environment"},
                        {"name": "tier"},
                        {"name": "type"},
                        {"name": "domain"},
                        {"name": "domain_controller"},
                    ],
                }
            ],
        },
    ],
}


def parse_record(text: str) -> tuple[str, dict[str, str]]:
    lines = text.split("\n")
    fields = {}
    for line in lines[1:]:
        key, sep, value = line.strip().partition(": ")
        if sep:
            fields[key] = value.strip()
        elif line.strip().endswith(":"):
            fields[line.strip()[:-1]] = ""
    return lines[0].strip(), fields


def when(text: str) -> datetime | None:
    text = text.strip().replace("Z", "").replace(" UTC", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def evidence(indicators: list[str]) -> dict:
    """The alert's telemetry lines as typed fields, using only the line kinds TypeSafe's published example alerts
    carry: process (the executable), file (where it lives), registry (hive and area), and the source-event count."""
    processes, file_areas, registry_areas = set(), set(), set()
    counts = {"process": 0, "file": 0, "registry": 0}
    source_events = 0
    for line in indicators:
        kind, _, value = line.partition(": ")
        kind, low = kind.strip().lower(), value.strip().lower()
        if kind in counts:
            counts[kind] += 1
        if kind == "process" and low:
            processes.add(low.split()[0].rsplit("\\", 1)[-1])
        elif kind == "file":
            for area, marker in (("system32", "\\system32\\"), ("temp", "\\temp\\"), ("appdata", "\\appdata\\"), ("program_files", "\\program files")):
                if marker in low:
                    file_areas.add(area)
        elif kind == "registry":
            hive = low.split("\\", 1)[0]
            registry_areas.add({"hkey_local_machine": "hklm", "hkey_current_user": "hkcu", "hkey_users": "hku"}.get(hive, hive))
            for area in ("services", "environment", "run"):
                if f"\\{area}" in low:
                    registry_areas.add(area)
        elif kind == "source events" and low.split()[0].isdigit():
            source_events = int(low.split()[0])
    return {
        "processes": sorted(processes) or ["none"],
        "file_areas": sorted(file_areas) or ["none"],
        "registry_areas": sorted(registry_areas) or ["none"],
        "n_process": counts["process"],
        "n_file": counts["file"],
        "n_registry": counts["registry"],
        "source_events": math.log10(1 + source_events),
    }


def situation(case: dict) -> dict:
    """The case's state as typed fields, by code alone."""
    state = case["state"]
    head, _, body = state["alert"].partition("\n")
    detector, _, title = head.partition(" | ")
    header = dict(re.findall(r"(asset|principal|observed): (.+?)(?:\s{2,}|$)", body.split("\n")[0]))
    observed = when(header.get("observed", ""))
    host, login = header.get("asset", "").lower(), header.get("principal", "").lower()
    events = re.search(r"events correlated: (\d+)", body)
    indicators = [ln for ln in body.split("\n")[1:] if ": " in ln and not ln.startswith("events correlated")]

    records = [parse_record(r) for r in state["context"]["records"]]
    names = {login}
    for source, f in records:
        if source == "activedirectory.user" and f.get("sAMAccountName", "").lower() == login:
            names.add(f.get("displayName", "").lower())
        if source == "okta.user" and f.get("profile.login", "").lower().startswith(login + "@"):
            names.add(f"{f.get('profile.firstName', '')} {f.get('profile.lastName', '')}".strip().lower())
    names.discard("")

    def mentions(f: dict[str, str]) -> bool:
        text = " ".join(f.values()).lower()
        return (host and host in text) or any(n in text for n in names)

    change, badge, away, factor_days, notes = "none", "none", "no", None, []
    for source, f in records:
        if source == "servicenow.change_request":
            notes.append(f.get("short_description", ""))
            start, end = when(f.get("planned_start_date", "")), when(f.get("planned_end_date", ""))
            in_window = bool(observed and start and end and start <= observed <= end)
            approved = f.get("approval", "").lower() == "approved"
            level = ("covers" if in_window and approved else "window") if mentions(f) else ("other" if in_window else "stale")
            change = max(change, level, key=["none", "stale", "other", "window", "covers"].index)
        elif source == "servicenow.incident":
            notes.append(f.get("short_description", ""))
        elif source == "lenel.badge_event" and f.get("cardholderName", "").lower() in names:
            t = when(f.get("timestamp", ""))
            if observed and t and t.date() == observed.date() and f.get("result", "") == "Granted":
                badge = "onsite"
        elif source == "workday.time_off" and f.get("workerName", "").lower() in names:
            start, end = when(f.get("startDate", "")), when(f.get("endDate", ""))
            if observed and start and end and start.date() <= observed.date() <= end.date() and f.get("status") == "Approved":
                away = "yes"
        elif source == "okta.factor" and f.get("profile.credentialId", "").lower().startswith(login):
            t = when(f.get("created", ""))
            if observed and t:
                days = max((observed - t).total_seconds() / 86400, 0)
                factor_days = days if factor_days is None else min(factor_days, days)

    explains = {"change": change, "badge": badge, "time_off": away}
    if factor_days is not None:
        explains["factor_age"] = math.log10(1 + factor_days)
    return {
        "alert": {
            "what": {
                "detector": detector.split("-")[0],
                "title": title,
                "kinds": sorted({ln.split(":")[0].strip() for ln in indicators}),
                "indicators": " ".join(ln.split(": ", 1)[1] for ln in indicators),
                "events": math.log10(1 + int(events.group(1))) if events else 0,
                "id": case["id"],
            },
            "evidence": evidence(indicators),
        },
        "context": {
            "explains": explains,
            "records": {"sources": sorted({s for s, _ in records}), "notes": " ".join(notes) or "none"},
        },
        "asset": {
            "where": {
                "environment": case["environment"],
                "tier": str(case["tier"]),
                "type": state["context"]["asset"]["type"],
                "domain": case["domain"],
                "domain_controller": str(case["domain_controller"]),
            }
        },
    }


# A yes/no (noul) answer is a probability, and the policy acts on where it falls against its cut-points (security.py,
# from TypeSafe's published threshold tests): a question's answer matters only up to which side of each cut-point
# it lands. So Ada learns a noul as the zones between that question's cut-points — "is this unauthorized?" as
# below 0.15 (close), 0.15-0.60 (notify), 0.60-0.75 (escalate), 0.75-0.90 (act), above 0.90 (act, purge mail) —
# and answers with its decided zone's midpoint, on the same side of every cut-point as the consensus it learned.
CUTS = {
    "is_true_positive": (0.15, 0.60, 0.75, 0.90),
    "context_explains_activity": (0.50,),
    "credentials_exposed": (0.40, 0.60),
    "session_in_attacker_hands": (0.50, 0.65),
    "malicious_content_in_mailboxes": (0.50,),
    "attacker_persistence_present": (0.60,),
    "malicious_process_running": (0.60,),
    "outbound_channel_active": (0.45,),
    "attacker_modified_configuration": (0.50,),
    "activity_ongoing": (0.50,),
    "spread_beyond_initial_entity": (0.50,),
}


def zones(q: str) -> dict[str, float]:
    """A noul question's zones between its cut-points, each named z0.. and valued at its midpoint."""
    edges = (0.0, *CUTS[q], 1.0)
    return {f"z{i}": round((lo + hi) / 2, 4) for i, (lo, hi) in enumerate(zip(edges, edges[1:], strict=False))}


def options(q: str, question: dict) -> list[str]:
    """The outcomes an Ada model of this question learns: the zones of a noul, the levels "0".. of a score, or
    the options of a choice."""
    if question["type"] == "noul":
        return list(zones(q))
    if question["type"] == "score":
        return [str(i) for i in range(len(question["criteria"]))]
    return list(question["criteria"])


def label(q: str, answer: float | dict[str, float]) -> str:
    """A reference's normalised answer as one outcome: a noul's P(yes) as its zone (a value exactly on a cut-point
    falls in the zone below it, as the policy's "P > cut" tests read it); a choice or score its likeliest option."""
    if isinstance(answer, float):
        return f"z{sum(answer > cut for cut in CUTS[q])}"
    return max(answer, key=answer.get)


def answer_workflow(cases: list[dict], situation) -> dict[str, dict]:
    """Ada in Jev's place in TypeSafe's workflow, compared exactly as Jev is: it answers the workflow's questions,
    and security.decide() — the same policy code — turns the answers into the action.

    One Ada model per question, used as the product is: record the other folds' cases, each graded with the
    consensus's answer to that question; refresh() (learn, then calibrate) once there are ten graded cases with two
    answers; decide() the held-out case. Its decided outcome is the answer, in the shape Jev's are: a noul its
    band's P(true), a choice or score its option. Where a model knows nothing near enough, it answers with its
    precedents' commonest answer."""
    reference = {c["id"]: run.consensus(c["id"]) for c in cases}
    folds = [cases[i::FOLDS] for i in range(FOLDS)]
    out = {}
    for i, fold in enumerate(folds):
        train = [c for j, f in enumerate(folds) if j != i for c in f]
        out.update(answer_cases(train_models(train, reference, situation), fold, situation))
    return out


def train_models(train: list[dict], reference: dict[str, dict], situation) -> dict:
    """One Ada model per workflow question, recorded from the training cases graded with the consensus's answer,
    learned and calibrated (refresh) once it holds ten graded cases with two answers; plus each question's base
    rates, the answer where a model declines."""
    import published
    import security

    questions = published.questions("security_incidents")
    models, base = {}, {}
    for q in (*security.TRIAGE, *security.CONTAINMENT):
        graded = [(c, label(q, reference[c["id"]][q])) for c in train if q in reference[c["id"]]]
        model = glyphh_spec.Model(glyphh_spec.Spec.from_json(SPEC), author="eval", path=None)
        for c, outcome in graded:
            model.record(situation(c), outcome)
        if len(graded) >= 10 and len({o for _, o in graded}) > 1:
            model.refresh()
        models[q] = model
        counts = Counter(o for _, o in graded)
        base[q] = {o: counts[o] / len(graded) for o in options(q, questions[q])}
    return {"models": models, "base": base, "questions": questions}


def answer_cases(trained: dict, cases: list[dict], situation) -> dict[str, dict]:
    """Each case through the workflow: the trained models answer, security.decide() turns the answers into the
    action."""
    import security

    models, base, questions = trained["models"], trained["base"], trained["questions"]

    def answer(q: str, data: dict) -> float | dict[str, float]:
        # decide()'s outcome, sharp as Jev's answers are: an averaged probability rarely reaches the policy's
        # thresholds (close below 0.15, act above 0.75). Declined (nothing near enough): the commonest answer.
        outcome = models[q].decide(data)["outcome"] or max(base[q], key=base[q].get)
        if questions[q]["type"] == "noul":
            return zones(q)[outcome]
        return {o: 1.0 if o == outcome else 0.0 for o in options(q, questions[q])}

    out = {}
    for c in cases:
        t0 = time.time()
        data = situation(c)
        action, answers = security.decide(lambda qs, data=data: {q: answer(q, data) for q in qs}, c)
        out[c["id"]] = {"action": action, "answers": answers, "seconds": time.time() - t0, "dollars": 0.0}
    return out


def main() -> None:
    """dev: five-fold cross-validation over the development cases. test: the models trained on every development
    case answer each test case once — the frozen setup's one score."""
    labels = score.consensus_actions()  # the same reference Jev is scored against, in this run's set
    if run.SET == "test":
        dev = run.cases("dev")
        reference = {c["id"]: run.consensus(c["id"], "dev") for c in dev}
        train = [c for c in dev if all(q in reference[c["id"]] for q in ("is_true_positive", "context_explains_activity"))]
        out = answer_cases(train_models(train, reference, situation), [c for c in run.cases() if c["id"] in labels], situation)
        how = f"trained on {len(train)} development cases"
    else:
        out = answer_workflow([c for c in run.cases() if c["id"] in labels], situation)
        how = f"{FOLDS}-fold"
    run.save("ada", out)
    right = sum(out[c]["action"] == labels[c] for c in out)
    print(f"ada ({run.SET}): {right} of {len(out)} match the consensus ({how})")


if __name__ == "__main__":
    main()
