"""How far ahead, and how far back, can Ada read along a thread of cases?

    python run.py ring          the control, whose best possible answer at every lead is known
    python run.py aapl-daily    44 years of daily cases
    python run.py aapl-hourly   three years of hourly bars
    python run.py baseball      a season's first 480 games, plate appearance by plate appearance, each game a thread

Each series is cut once, in time: the first 60% to learn from, the last 40% held out. Everything chosen (whether the
model learns pairs of roles, the halt threshold) is chosen inside the first 60%, on its last quarter, and fixed before
the held-out 40% is read. Every held-out case is asked as of its own time (`before`): no case from its time on is read,
neither as a case like it nor as a step after one.

Asked of every held-out case, at every lead: what will this output be that many cases on (predict), and what was it
that many cases back (lookback). Against two readers that need no model: the base rates so far, and "it stays as it
is". Results in results/<series>.json and results/<series>.txt."""

from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import ada_kernel  # noqa: E402

import series  # noqa: E402

glyphh_spec = ada_kernel.load()

LEARN, CHOOSE = 0.60, 0.45  # the held-out cut, and inside the first part the cut choices are made at
SMOOTH = 0.02  # every reader's probabilities are mixed with this much of the base rates before they are scored
HALTS = (0.005, 0.01, 0.02, 0.05, 0.1, 0.2)  # bits a step must say over the base rates to be acted on: the choices
PLANS = {
    # ahead: {output: (the lead its reading is learned at, the leads asked)}; back the same for lookback
    "ring": {
        "ahead": {"zone": (1, [1, 2, 3, 5, 8, 12, 20])},
        "back": {"zone": (1, [1, 2, 3, 5, 8, 12, 20])},
        "chain": {"zone": ([1, 2, 3, 5, 8, 12], 12, 8)},  # (leads, width, every n-th held-out case)
        "stride": 1,
    },
    "aapl-daily": {
        "ahead": {
            "dir": (1, [1, 2, 3, 5, 10, 20, 40, 60]),
            "size": (1, [1, 2, 3, 5, 10, 20, 40, 60]),
            "d5": (5, [5]),
            "d20": (20, [20]),
            "d60": (60, [60]),
        },
        "back": {"dir": (1, [1, 2, 3, 5, 10, 20]), "size": (1, [1, 2, 3, 5, 10, 20])},
        "chain": {"dir": ([1, 2, 3, 5], 3, 15), "size": ([1, 2, 3, 5], 3, 15)},
        "stride": 1,
    },
    "aapl-hourly": {
        "ahead": {
            "dir": (1, [1, 2, 3, 7, 14, 35]),
            "size": (1, [1, 2, 3, 7, 14, 35]),
            "d3": (3, [3]),
            "d6": (6, [6]),
        },
        "back": {"dir": (1, [1, 2, 3, 7, 14]), "size": (1, [1, 2, 3, 7, 14])},
        "chain": {"dir": ([1, 2, 3, 7], 3, 7), "size": ([1, 2, 3, 7], 3, 7)},
        "stride": 1,
    },
    "baseball": {
        "ahead": {
            "reach": (1, [1, 2, 3, 5, 9, 18]),
            "run": (1, [1, 2, 3, 5, 9, 18]),
            "kind": (1, [1, 2, 3, 5, 9, 18]),
        },
        "back": {"reach": (1, [1, 2, 3, 5, 9]), "run": (1, [1, 2, 3, 5, 9])},
        "chain": {"reach": ([1, 2, 3, 5], 8, 24), "run": ([1, 2, 3, 5], 8, 24)},
        "stride": 2,
        "thread": series.BASEBALL_THREAD,
    },
}


def build(spec: dict, cases: list[dict], learn_to: int, plan: dict, settings: dict) -> object:
    """A model that has learned from the cases before `learn_to` alone and holds every case (the later ones are
    there to be asked about with `before`, never learned from)."""
    model = glyphh_spec.Model(glyphh_spec.Spec.from_json({**spec, "settings": settings}))
    put = lambda rows: model.record_many([{k: c[k] for k in ("data", "ts", "outcomes")} for c in rows])  # noqa: E731
    put(cases[:learn_to])
    for output, (lead, _) in plan["ahead"].items():
        model.learn_thread(output, steps=lead, thread=plan.get("thread"))
    for output, (lead, _) in plan.get("back", {}).items():
        model.learn_thread(output, steps=lead, thread=plan.get("thread"), back=True)
    put(cases[learn_to:])
    return model


def mixed(p: dict[str, float], base: dict[str, float], true: str) -> float:
    return (1 - SMOOTH) * p.get(true, 0.0) + SMOOTH * base.get(true, 0.0)


def ask(model, cases: list[dict], rows: range, plan: dict, back: bool = False, chain: dict | None = None) -> list[dict]:
    """Every case of `rows` asked, as of its own time, at every lead of the plan. One record per (case, output,
    lead) whose truth is known: what was said, what was true, and what the two plain readers said."""
    counts: dict[str, Counter] = {o: Counter() for o in plan["ahead"]}
    seen = 0
    out = []
    asked = chain or plan["back" if back else "ahead"]
    for t in rows:
        while seen < t:  # the base rates so far: every case before this one
            for o in counts:
                counts[o][cases[seen]["outcomes"][o]] += 1
            seen += 1
        case = cases[t]
        for output, what in asked.items():
            leads = what[0] if chain else what[1]
            total = sum(counts[output].values())
            base = {o: n / total for o, n in counts[output].items()}
            commonest = max(base, key=lambda o: (base[o], o))
            read = model.lookback if back else model.predict
            kwargs = {"chain": True, "width": what[1]} if chain else {}
            answer = read(case["data"], leads, output, thread=plan.get("thread"), before=case["ts"], **kwargs)
            said = {s["step"]: s for s in answer["steps"]}
            for lead in leads:
                at = t - lead if back else t + lead
                if not 0 <= at < len(cases) or lead not in said:
                    continue
                if cases[at].get("thread") != case.get("thread"):  # that many steps on is another thread's case
                    continue
                true = cases[at]["outcomes"][output]
                step = said[lead]
                out.append(
                    {
                        "t": t,
                        "output": output,
                        "lead": lead,
                        "true": true,
                        "said": step["outcome"],
                        "p": mixed(step["probabilities"], base, true),
                        "gain": step["gain"],
                        "base": commonest,
                        "p_base": base.get(true, 0.0) or 1e-6,
                        "stays": case["outcomes"][output],
                        "lost": answer["lost"],
                    }
                )
    return out


def blocks(values: list[float], size: int) -> tuple[float, float]:
    """A mean and its standard error from the means of blocks of neighbouring cases: cases next to each other share
    their precedents and, at a lead over 1, most of their future, so they are not counted as independent."""
    if not values:
        return 0.0, 0.0
    means = [sum(values[i : i + size]) / len(values[i : i + size]) for i in range(0, len(values), size)]
    mean = sum(values) / len(values)
    if len(means) < 2:
        return mean, float("inf")
    var = sum((m - sum(means) / len(means)) ** 2 for m in means) / (len(means) - 1)
    return mean, math.sqrt(var / len(means))


def table(records: list[dict], halt: float | None = None) -> list[dict]:
    """Per output and lead: how often Ada, the base rates and "it stays" were right, Ada's lift over the better of
    the two with its standard error, and the bits Ada's probabilities say over the base rates'. With `halt`, the
    same split by whether the loop would still be acting at that lead (every nearer lead asked said `halt` bits)."""
    rows = []
    keys = sorted({(r["output"], r["lead"]) for r in records}, key=lambda k: (k[0], k[1]))
    halted_at: dict[tuple[int, str], int] = {}
    if halt is not None:
        for r in sorted(records, key=lambda r: r["lead"]):
            if r["gain"] < halt:
                halted_at.setdefault((r["t"], r["output"]), r["lead"])
    for output, lead in keys:
        mine = [r for r in records if r["output"] == output and r["lead"] == lead]
        mine.sort(key=lambda r: r["t"])
        size = max(20, 2 * lead)
        ada = [float(r["said"] == r["true"]) for r in mine]
        base = [float(r["base"] == r["true"]) for r in mine]
        stays = [float(r["stays"] == r["true"]) for r in mine]
        best = base if sum(base) >= sum(stays) else stays
        lift, se = blocks([a - b for a, b in zip(ada, best)], size)
        bits, bits_se = blocks([math.log2(r["p"] / r["p_base"]) for r in mine], size)
        row = {
            "output": output,
            "lead": lead,
            "n": len(mine),
            "ada": sum(ada) / len(ada),
            "base_rates": sum(base) / len(base),
            "stays": sum(stays) / len(stays),
            "lift": lift,
            "lift_se": se,
            "bits": bits,
            "bits_se": bits_se,
        }
        if halt is not None:
            acting = [r for r in mine if halted_at.get((r["t"], r["output"]), 10**9) > lead]
            resting = [r for r in mine if halted_at.get((r["t"], r["output"]), 10**9) <= lead]
            for name, part in (("acting", acting), ("halted", resting)):
                if part:
                    a = sum(r["said"] == r["true"] for r in part) / len(part)
                    b = max(
                        sum(r["base"] == r["true"] for r in part) / len(part),
                        sum(r["stays"] == r["true"] for r in part) / len(part),
                    )
                    row[name] = {"share": len(part) / len(mine), "ada": a, "best_plain": b, "lift": a - b}
        rows.append(row)
    return rows


def choose_halt(records: list[dict]) -> float:
    """The halt whose acting forecasts lift the most over the plain readers, summed over every output and lead,
    among those that keep acting on at least a fifth of the nearest lead."""
    best = (-1.0, HALTS[0])
    nearest = min(r["lead"] for r in records)
    for halt in HALTS:
        rows = table(records, halt)
        kept = [r["acting"]["share"] for r in rows if r["lead"] == nearest and "acting" in r]
        if not kept or min(kept) < 0.2:
            continue
        score = sum(r["acting"]["lift"] * r["acting"]["share"] for r in rows if "acting" in r)
        if score > best[0]:
            best = (score, halt)
    return best[1]


def show(title: str, rows: list[dict], extra: dict[tuple[str, int], dict] | None = None) -> list[str]:
    lines = [title, f"{'output':7}{'lead':>5}{'n':>6}{'Ada':>8}{'base':>8}{'stays':>8}{'lift':>8}{'± se':>7}{'bits':>8}{'± se':>7}"]
    for r in rows:
        line = (
            f"{r['output']:7}{r['lead']:>5}{r['n']:>6}{r['ada']:>8.1%}{r['base_rates']:>8.1%}{r['stays']:>8.1%}"
            f"{r['lift']:>+8.1%}{r['lift_se']:>7.1%}{r['bits']:>+8.3f}{r['bits_se']:>7.3f}"
        )
        for name in ("acting", "halted"):
            if name in r:
                line += f"   {name} {r[name]['share']:.0%}: {r[name]['ada']:.1%} ({r[name]['lift']:+.1%})"
        if extra and (r["output"], r["lead"]) in extra:
            line += "   " + "  ".join(f"{k} {v:.1%}" for k, v in extra[(r["output"], r["lead"])].items())
        lines.append(line)
    return lines


def main(name: str) -> None:
    plan = PLANS[name]
    started = time.time()
    spec, cases = series.ring(6000) if name == "ring" else series.baseball(480) if name == "baseball" else series.market(name)
    n = len(cases)
    cut, inner = int(n * LEARN), int(n * CHOOSE)
    furthest = max(max(leads) for _, leads in plan["ahead"].values())
    out: dict = {"series": name, "cases": n, "learned_from": cut, "held_out": n - cut, "smooth": SMOOTH}
    lines = [f"{name}: {n} cases, the first {cut} learned from, the last {n - cut} held out"]

    # chosen inside the first part: pairs of roles or not, and the halt
    chosen = {}
    for pairs in (True, False):
        model = build(spec, cases[:cut], inner, plan, {"interactions": pairs})
        records = ask(model, cases[:cut], range(inner, cut - furthest, 3), plan)
        rows = table(records)
        chosen[pairs] = (sum(r["bits"] for r in rows) / len(rows), records)
        print(f"  choosing: pairs {pairs}: {chosen[pairs][0]:+.4f} bits a forecast  ({time.time() - started:.0f}s)", file=sys.stderr)
        del model
    pairs = chosen[True][0] > chosen[False][0]
    halt = choose_halt(chosen[pairs][1])
    out["chosen"] = {"interactions": pairs, "halt": halt, "bits": {str(k): v[0] for k, v in chosen.items()}}
    lines.append(f"chosen before the held-out part: pairs of roles {'on' if pairs else 'off'}, halt {halt} bits")

    model = build(spec, cases, cut, plan, {"interactions": pairs})
    held = range(cut, n, plan["stride"])
    ahead = ask(model, cases, held, plan)
    out["ahead"] = table(ahead, halt)
    extra = None
    if name == "ring":
        leads = plan["ahead"]["zone"][1]
        out["ceiling"] = {"ahead": series.ceiling(leads), "back": series.ceiling(leads, back=True)}
        extra = {("zone", k): {"best possible": v["best"]} for k, v in out["ceiling"]["ahead"].items()}
    lines += ["", *show("AHEAD (predict), held out", out["ahead"], extra)]
    print(f"  ahead done ({time.time() - started:.0f}s)", file=sys.stderr)

    back = ask(model, cases, held, plan, back=True)
    out["back"] = table(back)
    if name == "ring":
        extra = {("zone", k): {"best possible": v["best"]} for k, v in out["ceiling"]["back"].items()}
    lines += ["", *show("BACK (lookback), held out", out["back"], extra)]
    print(f"  back done ({time.time() - started:.0f}s)", file=sys.stderr)

    # the beam, one step at a time, against each step read on its own, on the same held-out cases
    every = max(what[2] for what in plan["chain"].values())
    some = range(cut, n, every)
    beam = ask(model, cases, some, plan, chain=plan["chain"])
    direct = [r for r in ahead if r["t"] in some and r["output"] in plan["chain"] and r["lead"] in plan["chain"][r["output"]][0]]
    out["beam"] = {"beam": table(beam), "each_step_alone": table(direct), "lost": sum(r["lost"] for r in beam) / max(len(beam), 1)}
    lines += ["", *show(f"THE BEAM, one step at a time (every {every}th held-out case)", out["beam"]["beam"])]
    lines += [*show("the same cases and leads, each step read on its own", out["beam"]["each_step_alone"])]
    lines.append(f"mass the beam cut, on average: {out['beam']['lost']:.1%}")

    out["seconds"] = round(time.time() - started)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{name}.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "results" / f"{name}.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ring")
