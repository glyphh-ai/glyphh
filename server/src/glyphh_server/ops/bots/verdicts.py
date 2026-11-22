"""The Resume Screener's verdicts (ops/bots/builtins.py `screen_verdicts`): each applicant's gates' calls put together,
so one step's data answers for all of them (the connector's screen_application and applicants read it): whether the
sender is real, how well they fit the role (strong, borderline or poor), and how much of the application was
generated (some, mostly or fully; human when the probe found no close generated precedent, ops/bots/probe.py), each
with its confidence (Ada's probability of the outcome, or 1 where the person said it) and who decided it."""

from typing import Any

FITS: tuple[str, ...] = ("strong", "borderline", "poor")
LABELS: dict[str, str] = {
    "strong": "Screened/Strong", "borderline": "Screened/Borderline", "poor": "Screened/Poor", "spam": "Screened/Spam",
}  # fmt: skip
SCREENED: str = "Screened"


def _by_key(decisions: Any) -> dict[str, dict[str, Any]]:
    return {str(d.get("key")): d for d in decisions or [] if isinstance(d, dict)}


def _call(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if d is None or d.get("outcome") is None:
        return None
    p = 1.0 if d.get("by") == "person" else d.get("p")
    return {"outcome": d["outcome"], "confidence": None if p is None else round(float(p), 2), "by": d.get("by")}


def _human(probed: Any) -> dict[str, dict[str, Any]]:
    """The applications the probe found written by a person: {id: the call, with how near the nearest came}."""
    probed = probed if isinstance(probed, dict) else {}
    floor = (probed.get("reference") or {}).get("p5")
    return {
        str(h.get("id")): {"outcome": "human", "confidence": None, "by": "probe", "nearest": h.get("nearest"),
                           "reference": floor}
        for h in probed.get("human") or [] if isinstance(h, dict)
    }  # fmt: skip


def _verdict(source: Any, fit: Any) -> str:
    if source is None:
        return "waiting"
    if source["outcome"] == "spam":
        return "spam"
    return fit["outcome"] if fit else "waiting"


def merged(given: dict[str, Any]) -> dict[str, Any]:
    """{applications, rejected, source, fit, probe, made} (the gates' `decisions`, the probe's data) →
    {verdicts, rejected, summary}."""
    source, fit, made = (_by_key(given.get(k)) for k in ("source", "fit", "made"))
    human = _human(given.get("probe"))
    out = []
    for a in given.get("applications") or []:
        key = str(a.get("id"))
        calls = {"source": _call(source.get(key)), "fit": _call(fit.get(key)), "made": _call(made.get(key))}
        out.append({
            "id": key, "name": a.get("name"), "email": a.get("email"), "role": a.get("role"),
            "subject": a.get("subject"), "years": a.get("years"), "skills": a.get("skills"),
            "verdict": _verdict(calls["source"], calls["fit"]), "fit": calls["fit"],
            "generated": calls["made"] or human.get(key), "source": calls["source"],
        })  # fmt: skip
    rejected = list(given.get("rejected") or [])
    counts = {v: sum(1 for x in out if x["verdict"] == v) for v in (*FITS, "spam", "waiting")}
    summary = ", ".join(f"{n} {v}" for v, n in counts.items() if n) or "no new applications"
    if rejected:
        summary += f"; {len(rejected)} refused by the sender checks"
    return {"verdicts": out, "rejected": rejected, "summary": summary}


def marks(given: dict[str, Any]) -> dict[str, list[str]]:
    """The inbox labels for a run's verdicts: every screened message Screened, and its verdict's label beside it
    (a refused one Screened/Spam); a resume the person handed in has no message to label."""
    out: dict[str, list[str]] = {SCREENED: [], **{name: [] for name in LABELS.values()}}
    for v in given.get("verdicts") or []:
        if str(v.get("id", "")).startswith("given-") or v.get("verdict") not in LABELS:
            continue
        out[SCREENED].append(str(v["id"]))
        out[LABELS[v["verdict"]]].append(str(v["id"]))
    for r in given.get("rejected") or []:
        if not str(r.get("id", "")).startswith("given-"):
            out[SCREENED].append(str(r["id"]))
            out[LABELS["spam"]].append(str(r["id"]))
    return {name: ids for name, ids in out.items() if ids}
