"""What a bot's gates have learned, for people: `gate_stats` (JSON, `glyphh bot gates`) and `write_report` (a
self-contained HTML page in the bot's folder, `glyphh bot report`): the last run's items with each decision, who
made it and how sure; how often the bot asked, decided alone and was overruled; its ask rate run by run; and each
gate's record. A bot's program may still write its own artifacts beside it (into `out/`); the report links them."""

from __future__ import annotations

import datetime as dt
import html
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from .. import __version__

if TYPE_CHECKING:  # pragma: no cover
    from .runner import Runner

#: The decisions that count toward a bot's ask rate (a program's own calls and ladders never ask).
ASKING = ("gate", "each", "approval")
#: The report's colours: a dark page; no label darker than #999.
PALETTE = ("#5eead4", "#fbbf24", "#a78bfa", "#fca5a5", "#60a5fa", "#f9a8d4")


def _rate(a: int, b: int) -> Optional[float]:
    return round(a / b, 3) if b else None


def _overruled(r: Mapping[str, Any]) -> Optional[str]:
    """Why a decision counts as overruled: a correction, an audit the person disagreed with, or the world."""
    if r.get("wrong") and r["wrong"] != r["outcome"]:
        return "wrong"
    if r.get("mode") == "audit" and r.get("agreed") == 0:
        return "audit"
    if r.get("kind") != "ladder" and r.get("world") and r["world"] != r["outcome"] and r.get("by") == "ada":
        return "world"
    return None


def gate_stats(runner: "Runner", runs: int = 10) -> Dict[str, Any]:
    """Per gate: its precedents, its policy, decisions by Ada vs the person (and defaults), its ask rate over the last
    `runs` runs (and run by run), agreement on audits and shadow calls, overrules, world outcomes still waiting."""
    from .gates import POLICY
    from .runner import held

    recent = list(reversed(runner.store.recent(runs)))
    run_ids = [r["id"] for r in recent]
    rows = runner.store.decisions()
    out: Dict[str, Any] = {}
    for name, gate in runner.bot.gates.items():
        mine = [r for r in rows if r["gate"] == name]
        window = [r for r in mine if r["run"] in run_ids]
        asking = [r for r in window if r["kind"] in ASKING]
        by = Counter(r["by"] for r in mine)
        by_run = []
        for rid in run_ids:
            rr = [r for r in asking if r["run"] == rid]
            if rr:
                n = sum(1 for r in rr if r["by"] == "person")
                by_run.append({"run": rid, "asked": n, "of": len(rr), "rate": _rate(n, len(rr))})

        def agreement(mode: str) -> Dict[str, Any]:
            got = [r for r in mine if r["mode"] == mode and r["by"] == "person" and r["agreed"] is not None]
            agreed = sum(1 for r in got if r["agreed"])
            return {"asked": len(got), "agreed": agreed, "rate": _rate(agreed, len(got))}

        guessed = [r for r in mine if r["by"] == "person" and r["agreed"] is not None]
        why = Counter(w for w in (_overruled(r) for r in mine) if w)
        ladder = [r for r in mine if r["kind"] == "ladder"]
        entry: Dict[str, Any] = {
            "precedents": held(runner.ada, runner.bot.gate_model(name)),
            "outcomes": list(gate.get("outcomes") or []),
            "policy": {k: gate[k] for k in POLICY if k in gate},
            "decisions": {"ada": by.get("ada", 0), "person": by.get("person", 0), "default": by.get("default", 0),
                          "total": len(mine)},
            "ask_rate": _rate(sum(1 for r in asking if r["by"] == "person"), len(asking)),
            "ask_rate_by_run": by_run,
            "audit": agreement("audit"),
            "shadow": agreement("shadow"),
            "agreement": {"asked": len(guessed), "agreed": sum(1 for r in guessed if r["agreed"]),
                          "rate": _rate(sum(1 for r in guessed if r["agreed"]), len(guessed))},
            "overrules": {"wrong": why.get("wrong", 0), "audit": why.get("audit", 0), "world": why.get("world", 0),
                          "total": sum(why.values())},
        }
        if gate.get("world"):
            entry["world"] = {"recorded": sum(1 for r in mine if r["world"]),
                              "waiting": sum(1 for r in mine if not r["world"] and r["kind"] != "code")}
        if ladder:
            entry["ladder"] = {"runs": len(ladder), "worked": sum(1 for r in ladder if r["world"]),
                               "escalated": sum(1 for r in ladder if r["world"] and r["world"] != r["outcome"]),
                               "took": dict(Counter(r["world"] for r in ladder if r["world"]))}
        out[name] = entry
    return {"bot": runner.bot.slug, "runs": len(run_ids), "gates": out}


def ask_rates(runner: "Runner", runs: int = 30) -> List[Dict[str, Any]]:
    """Every gate together, run by run (oldest first): how many of its asking decisions went to the person."""
    recent = list(reversed(runner.store.recent(runs)))
    rows = [r for r in runner.store.decisions() if r["kind"] in ASKING]
    found = []
    for run in recent:
        rr = [r for r in rows if r["run"] == run["id"]]
        if rr:
            n = sum(1 for r in rr if r["by"] == "person")
            found.append({"run": run["id"], "asked": n, "of": len(rr), "rate": n / len(rr)})
    return found


def _sparkline(points: List[Dict[str, Any]], width: int = 560, height: int = 120) -> str:
    if not points:
        return '<p class="muted">No run has passed a gate yet.</p>'
    pad, n = 18, len(points)
    xs = [pad + (width - 2 * pad) * (i / (n - 1) if n > 1 else 0.5) for i in range(n)]
    ys = [pad + (height - 2 * pad) * (1 - p["rate"]) for p in points]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    area = f"{path} L{xs[-1]:.1f},{height - pad} L{xs[0]:.1f},{height - pad} Z"
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5"><title>{html.escape(p["run"])}: asked {p["asked"]} of {p["of"]}'
        f'</title></circle>' for x, y, p in zip(xs, ys, points)
    )
    first, last = points[0]["rate"], points[-1]["rate"]
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Ask rate run by run, from '
        f'{first:.0%} to {last:.0%}">'
        f'<line x1="{pad}" y1="{pad}" x2="{width - pad}" y2="{pad}" class="grid"/>'
        f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" class="grid"/>'
        f'<text x="{pad}" y="{pad - 5}" class="axis">100%</text>'
        f'<text x="{pad}" y="{height - 4}" class="axis">0%</text>'
        f'<path d="{area}" class="area"/><path d="{path}" class="line"/>{dots}'
        f'<text x="{xs[-1]:.1f}" y="{max(ys[-1] - 9, 12):.1f}" class="end" text-anchor="end">{last:.0%}</text>'
        f"</svg>"
    )


CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0b0f14; color: #e8eaed; font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
  Inter, Roboto, sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 40px 24px 64px; }
h1 { font-size: 28px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; color: #a8b0ba; margin: 40px 0 12px; }
.muted, .label { color: #a8b0ba; }
.summary { color: #c9cfd6; margin: 0 0 6px; }
.meta { color: #a8b0ba; font-size: 13px; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 28px; }
.card { background: #121821; border: 1px solid #1f2833; border-radius: 14px; padding: 18px 20px; }
.card .n { font-size: 40px; font-weight: 650; letter-spacing: -0.02em; line-height: 1.1; }
.card .label { font-size: 13px; }
.card .sub { color: #a8b0ba; font-size: 12px; margin-top: 6px; }
.asked .n { color: #fbbf24; } .alone .n { color: #5eead4; } .over .n { color: #fca5a5; }
.panel { background: #121821; border: 1px solid #1f2833; border-radius: 14px; padding: 18px 20px; }
svg .grid { stroke: #2a3441; stroke-width: 1; } svg .axis { fill: #a8b0ba; font-size: 11px; }
svg .line { fill: none; stroke: #5eead4; stroke-width: 2.5; stroke-linejoin: round; }
svg .area { fill: rgba(94, 234, 212, 0.10); } svg circle { fill: #0b0f14; stroke: #5eead4; stroke-width: 2; }
svg .end { fill: #e8eaed; font-size: 13px; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: #a8b0ba; font-weight: 500; font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.06em; padding: 8px 10px; border-bottom: 1px solid #1f2833; }
td { padding: 9px 10px; border-bottom: 1px solid #161d26; vertical-align: top; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.chip { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
  border: 1px solid currentColor; }
.who { font-size: 13px; } .who.person { color: #fbbf24; } .who.ada { color: #5eead4; } .who.default,
.who.deferred { color: #a8b0ba; }
.bar { display: inline-block; width: 64px; height: 6px; background: #1f2833; border-radius: 3px; margin-right: 8px;
  vertical-align: middle; } .bar i { display: block; height: 100%; border-radius: 3px; background: #5eead4; }
.note { color: #a8b0ba; font-size: 12px; }
.disagree { color: #fca5a5; font-size: 12px; } .agree { color: #5eead4; font-size: 12px; }
a { color: #7dd3fc; }
footer { margin-top: 48px; color: #a8b0ba; font-size: 12px; }
@media (max-width: 700px) { .cards { grid-template-columns: 1fr; } }
"""


def _chip(outcome: Optional[str], colours: Mapping[str, str]) -> str:
    if not outcome:
        return '<span class="note">waits</span>'
    return f'<span class="chip" style="color:{colours.get(outcome, "#e8eaed")}">{html.escape(outcome)}</span>'


def _who(by: Optional[str]) -> str:
    said = {"person": "you", "ada": "Ada", "default": "default", "deferred": "next run", "unsure": "program"}.get(
        by or "", by or "")
    return f'<span class="who {html.escape(by or "")}">{html.escape(said)}</span>'


def _pbar(p: Optional[float]) -> str:
    if p is None:
        return '<span class="note">new</span>'
    return f'<span class="bar"><i style="width:{max(0.0, min(1.0, p)) * 100:.0f}%"></i></span>{p:.2f}'


def render(runner: "Runner", runs: int = 30) -> str:
    """The report's HTML, self-contained (no script, no outside file)."""
    bot = runner.bot
    stats = gate_stats(runner, runs)
    points = ask_rates(runner, runs)
    all_rows = runner.store.decisions()
    asking = [r for r in all_rows if r["kind"] in ASKING]
    asked = sum(1 for r in asking if r["by"] == "person")
    alone = sum(1 for r in asking if r["by"] == "ada")
    over = sum(1 for r in all_rows if _overruled(r))
    last = runner.store.recent(1)
    last_run = last[0] if last else None
    gated = [r["run"] for r in all_rows if r["kind"] != "code"]
    shown_run = gated[-1] if gated else None
    last_rows = [r for r in all_rows if r["run"] == shown_run and r["kind"] != "code"]
    shown_title = ("The last run's decisions" if last_run and shown_run == last_run["id"]
                   else f"The decisions of run {shown_run}, the last that passed a gate" if shown_run
                   else "The last run's decisions")
    colours: Dict[str, str] = {}
    for gate in bot.gates.values():
        for i, o in enumerate(gate.get("outcomes") or []):
            colours.setdefault(o, PALETTE[i % len(PALETTE)])
    e = html.escape
    trust = runner.trust()
    when = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if last_run:
        la = sum(1 for r in last_rows if r["kind"] in ASKING and r["by"] == "person")
        ld = sum(1 for r in last_rows if r["kind"] in ASKING and r["by"] == "ada")
        run_line = (f"Last run {e(last_run['id'])}: {e(last_run['status'])}"
                    f"{': ' + e(last_run['reason']) if last_run['reason'] else ''}")
        last_sub = f"the last gated run: {la}" if shown_run else "no gate passed yet"
        alone_sub = f"the last gated run: {ld}" if shown_run else "no gate passed yet"
    else:
        run_line, last_sub, alone_sub = "No run yet.", "no run yet", "no run yet"
    items = []
    for r in last_rows:
        agreed = ""
        if r["by"] == "person" and r["agreed"] is not None and r["mode"] in ("audit", "shadow", "unsure", "few"):
            agreed = (f'<span class="agree">Ada guessed {e(r["guess"] or "")}: agreed</span>' if r["agreed"]
                      else f'<span class="disagree">Ada guessed {e(r["guess"] or "")}: you overruled</span>')
        fixed = f'<span class="disagree">corrected to {e(r["wrong"])}</span>' if r["wrong"] else ""
        world = f'<span class="note">the world: {e(r["world"])}</span>' if r["world"] else ""
        mode = {"audit": "audit", "shadow": "shadow", "new": "no precedents", "few": "too few precedents",
                "unsure": "not sure", "ada": ""}.get(r["mode"] or "", r["mode"] or "")
        items.append(
            f"<tr><td class=num>{r['n'] or ''}</td><td>{e(r['label'] or r['step'])}"
            f"<div class=note>{e(r['gate'])}{' · ' + e(mode) if mode else ''}</div></td>"
            f"<td>{_chip(r['outcome'], colours)}</td><td>{_who(r['by'])}</td><td class=num>{_pbar(r['p'])}</td>"
            f"<td>{agreed} {fixed} {world}</td></tr>"
        )
    items_html = (
        "<table><thead><tr><th>#</th><th>Item</th><th>Decision</th><th>Who</th><th>P</th><th></th></tr></thead>"
        f"<tbody>{''.join(items)}</tbody></table>" if items else '<p class="muted">The last run passed no gate.</p>'
    )
    gates_rows = []
    for name, g in stats["gates"].items():
        rate = "–" if g["ask_rate"] is None else f"{g['ask_rate']:.0%}"
        aud = g["audit"]
        sh = g["shadow"]
        checks = []
        if aud["asked"]:
            checks.append(f"audits {aud['agreed']}/{aud['asked']} agreed")
        if sh["asked"]:
            checks.append(f"shadow {sh['agreed']}/{sh['asked']} agreed")
        if g.get("ladder"):
            lad = g["ladder"]
            checks.append(f"ladder: {lad['escalated']} of {lad['runs']} escalated")
        if g.get("world"):
            checks.append(f"world: {g['world']['recorded']} recorded, {g['world']['waiting']} waiting")
        policy = ", ".join(f"{k} {v}" for k, v in g["policy"].items())
        gates_rows.append(
            f"<tr><td>{e(name)}<div class=note>{e(' / '.join(g['outcomes']))}</div></td><td class=num>{g['precedents']}</td>"
            f"<td class=num>{g['decisions']['ada']}</td><td class=num>{g['decisions']['person']}</td>"
            f"<td class=num>{g['decisions']['default']}</td><td class=num>{rate}</td>"
            f"<td class=num>{g['overrules']['total']}</td><td class=note>{e('; '.join(checks) or '–')}"
            f"{'<br>' + e(policy) if policy else ''}</td></tr>"
        )
    out_dir = bot.dir / "out"
    files = sorted((p for p in out_dir.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:8] \
        if out_dir.exists() else []
    made = "".join(f'<li><a href="{e(p.relative_to(bot.dir).as_posix())}">{e(p.relative_to(bot.dir).as_posix())}</a></li>'
                   for p in files)
    first_rate = f"{points[0]['rate']:.0%}" if points else "–"
    last_rate = f"{points[-1]['rate']:.0%}" if points else "–"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(bot.name)}: what its gates learned</title><style>{CSS}</style></head>
<body><main>
<h1>{e(bot.name)}</h1>
<p class="summary">{e(str(bot.spec.get("summary") or ""))}</p>
<div class="meta">{run_line} · trust {e(trust)} · {stats['runs']} runs read</div>
<div class="cards">
  <div class="card asked"><div class="n">{asked}</div><div class="label">times it asked you</div><div class="sub">{last_sub}</div></div>
  <div class="card alone"><div class="n">{alone}</div><div class="label">decided by itself</div><div class="sub">{alone_sub}</div></div>
  <div class="card over"><div class="n">{over}</div><div class="label">times you overruled it</div><div class="sub">corrections, audits and real outcomes</div></div>
</div>
<h2>Ask rate, run by run · {first_rate} → {last_rate}</h2>
<div class="panel">{_sparkline(points)}</div>
<h2>{e(shown_title)}</h2>
<div class="panel">{items_html}</div>
<h2>The gates</h2>
<div class="panel"><table><thead><tr><th>Gate</th><th>Precedents</th><th>Ada</th><th>You</th><th>Default</th>
<th>Ask rate</th><th>Overruled</th><th>Checks</th></tr></thead><tbody>{''.join(gates_rows)}</tbody></table></div>
{'<h2>What it made</h2><div class="panel"><ul>' + made + '</ul></div>' if made else ''}
<footer>Made by glyphh {e(__version__)} on {e(when)}. Learned gates learn only from your answers, your corrections and
real outcomes; hard gates are the bot's code.</footer>
</main></body></html>
"""


def write_report(runner: "Runner", runs: int = 30) -> Dict[str, Any]:
    """The report, written to the bot's folder as report.html."""
    path = runner.bot.dir / "report.html"
    path.write_text(render(runner, runs), "utf-8")
    stats = ask_rates(runner, runs)
    return {"bot": runner.bot.slug, "report": str(path),
            "ask_rate": {"first": stats[0]["rate"] if stats else None, "last": stats[-1]["rate"] if stats else None,
                         "runs": len(stats)}}
