"""The checks of docs/checks.md, run on real Ada. Each takes `ada`, an async function (method, path, body) that
calls Ada Cloud's API and answers its JSON, so the same code runs against any Ada: `run.py` gives it one for your
own account. Only train rows of the corpus are read. No model other than Ada is used anywhere."""

import asyncio
import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import corpus as seed
import rings
from screener import others, steps, timing

Ada = Callable[..., Awaitable[Any]]
VALIDATION_EACH: int = 4
T0: datetime = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def train(corpus: Path) -> list[dict[str, Any]]:
    return seed.rows(corpus, "train")


def spread(sims: list[float]) -> dict[str, Any]:
    ranked = sorted(sims)
    cut = {f"p{p}": round(ranked[max(0, math.ceil(p / 100 * len(ranked)) - 1)], 4) for p in (5, 25, 50, 75, 95)}
    return cut | {"n": len(ranked), "min": round(ranked[0], 4), "max": round(ranked[-1], 4)} if ranked else {"n": 0}


async def make(ada: Ada, name: str, model: str) -> None:
    await ada("POST", "/v1/models", {"name": name, "spec": steps.models()[model]["spec"] | {"name": name}})


async def hold(ada: Ada, name: str, cases: list[dict[str, Any]], chunk: int = 250) -> None:
    for at in range(0, len(cases), chunk):
        await ada("POST", f"/v1/models/{name}/record_many", {"cases": cases[at : at + chunk]})


async def learn(ada: Ada, name: str) -> None:
    job = await ada("POST", f"/v1/models/{name}/learn", {})
    while job.get("state") not in ("done", "failed"):
        await asyncio.sleep(0.5)
        job = await ada("GET", f"/v1/jobs/{job['id']}")
    assert job["state"] == "done", json.dumps(job.get("error"))[:1000]


# Check 0: the plugin reads an application as the earlier build did.


def validation(rows: list[dict[str, Any]]) -> set[str]:
    cells: dict[tuple[str, str, str], list[str]] = {}
    for r in rows:
        cells.setdefault((r["role"], r["fit"], r["generated"]), []).append(r["id"])
    order = lambda i: hashlib.sha256(f"glyphh-validation-1:{i}".encode()).hexdigest()  # noqa: E731
    return {i for ids in cells.values() for i in sorted(ids, key=order)[:VALIDATION_EACH]}


async def carried_over(ada: Ada, corpus: Path) -> dict[str, Any]:
    rows = train(corpus)
    held = validation(rows)
    read = {r["id"]: seed.precedents(corpus, r) for r in rows}
    out: dict[str, Any] = {"design rows": len(rows) - len(held), "validation rows": len(held)}
    for model in ("fit", "made"):
        name = f"check0-{model}"
        await make(ada, name, model)
        await hold(ada, name, [read[r["id"]][model] for r in rows if r["id"] not in held and read[r["id"]]])
        await learn(ada, name)
        table: Counter[str] = Counter()
        asked = 0
        for r in (r for r in rows if r["id"] in held):
            case = read[r["id"]][model]
            said = await ada("POST", f"/v1/models/{name}/decide", {"data": case["data"]})
            table[f"{case['outcome']}>{said.get('outcome') or 'no answer'}"] += 1
            asked += bool(said.get("ask"))
        right = sum(n for k, n in table.items() if k.split(">")[0] == k.split(">")[1])
        out[model] = {"right": right, "accuracy": round(right / len(held), 4), "asked": asked,
                      "confusion": dict(sorted(table.items()))}  # fmt: skip
    return out


# Check 1: this application against the others.


async def asked(ada: Ada, name: str, case: dict[str, Any]) -> dict[str, Any]:
    """The `others` step's answer for the case, with Ada asked one part at a time."""
    near = {}
    for part in others.PARTS:
        if part in case:
            got = await ada("POST", f"/v1/models/{name}/facts", {"data": {part: case[part]}, "top": others.TOP})
            near[part] = others.nearest(got)
    return others.compared(lambda q: near[next(iter(q))], case)


async def against_the_others(ada: Ada, corpus: Path, mode: str) -> dict[str, Any]:
    """`mode` design: the design rings and controls; heldout: the one held-out run."""
    split = rings.groups(train(corpus))
    design = mode == "design"
    bases = split["design bases" if design else "held bases"]
    controls = split["design controls" if design else "held controls"]
    held = split["population"] + ([] if design else split["design bases"] + split["design controls"]) + bases
    name = f"check1-{mode}"
    await make(ada, name, "others")
    await hold(ada, name, [{"data": rings.case_of(r["id"], rings.parts_of(r)), "outcome": "alone"} for r in held])
    flags: dict[str, Counter[str]] = {v: Counter() for v in (*rings.VARIANTS, "control")}
    caught: Counter[str] = Counter()
    right: Counter[str] = Counter()
    sims: dict[str, list[float]] = {}

    def note(variant: str, got: dict[str, Any], base: str = "") -> None:
        flags[variant].update(got["flags"])
        caught[variant] += bool(set(got["flags"]) - {"none", "applied_before"})
        right[variant] += any(v["id"] == base for v in got["near"].values())
        for part, v in got["near"].items():
            sims.setdefault(f"{variant} {part}", []).append(v["sim"])

    for n, base in enumerate(bases):
        mine, donor = rings.parts_of(base), rings.parts_of(bases[(n + 1) % len(bases)])
        stranger = rings.parts_of(controls[n % len(controls)])
        new = rings.renamed(mine, n)
        made = {"renamed": new, "reworded": rings.reworded(new), "reordered": rings.reordered(new),
                "one job changed": rings.one_job_changed(new, donor),
                "shared contact": rings.shared_contact(stranger, mine)}  # fmt: skip
        for variant, parts in made.items():
            note(variant, await asked(ada, name, rings.case_of(f"{base['id']}-{variant}", parts)), base["id"])
        copies = [rings.case_of(f"{base['id']}-copy{i}", rings.renamed(mine, 1000 + n * 10 + i)) for i in range(4)]
        await hold(ada, name, [{"data": c, "outcome": "alone"} for c in copies])
        fifth = await asked(ada, name, rings.case_of(f"{base['id']}-fifth", rings.renamed(mine, 5000 + n)))
        flags["burst"].update(fifth["flags"])
        caught["burst"] += "burst" in fifth["flags"]
    for row in controls:
        note("control", await asked(ada, name, rings.case_of(row["id"], rings.parts_of(row))))
    return {"mode": mode, "held": len(held), "bases": len(bases), "controls": len(controls),
            "ceilings": others.CEILING, "caught": dict(caught), "flags": {k: dict(v) for k, v in flags.items()},
            "names the base": dict(right), "nearest": {k: spread(v) for k, v in sorted(sims.items())}}  # fmt: skip


# Check 2b: applications arriving together.


def arrival(mid: str, at: datetime) -> dict[str, Any]:
    """A message as the `others` model holds its arrival: only the ten minutes it arrived in."""
    who = {"name": mid, "label": mid, "id": mid}
    tag = json.dumps([mid, mid, mid])
    return {"when": {"s": {"windows": timing.windows(at), "when_who": tag}}, "who": {"s": who}}


async def arriving_together(ada: Ada, mode: str) -> dict[str, Any]:
    """Groups 0 to 9 are the design groups, 10 to 39 the held-out ones; every group is held either way."""
    name = f"check2b-{mode}"
    await make(ada, name, "others")
    bases = [T0 + timedelta(hours=3 * g, seconds=97 * g) for g in range(40)]
    sent = [(f"g{g}-m{m}", base + timedelta(minutes=m)) for g, base in enumerate(bases) for m in range(5)]
    sent += [(f"g{g}-lone", base + timedelta(minutes=90)) for g, base in enumerate(bases)]
    await hold(ada, name, [{"data": arrival(mid, at), "outcome": "alone"} for mid, at in sent])
    mine = range(10) if mode == "design" else range(10, 40)
    out: dict[str, Any] = {"mode": mode, "groups": len(mine), "ceiling": others.CEILING["when"]}
    for kind, minutes in (("near", 2.5), ("far", 45)):
        together, sims = [], []
        for g in mine:
            case = arrival(f"g{g}-{kind}", bases[g] + timedelta(minutes=minutes))
            got = await ada("POST", f"/v1/models/{name}/facts", {"data": {"when": case["when"]}, "top": others.TOP})
            sims += [n["sim"] for n in others.nearest(got)]
            together.append((await asked(ada, name, case))["together"])
        out[kind] = {"burst named": sum(n >= timing.BURST for n in together), "together": dict(Counter(together)),
                     "every similarity answered": dict(Counter(round(s, 2) for s in sims))}  # fmt: skip
    return out


# Check 2c: the timing model learns the person's answers.


def crafted(seed_: int = 7) -> list[tuple[str, dict[str, Any], str]]:
    """60 crafted emails as (id, the timing as read, the answer taught): 30 ordinary, then 10 of each fault."""
    rng = random.Random(seed_)
    out = []
    for i in range(60):
        kind = "ordinary" if i < 30 else ("ahead", "disorder", "slow")[(i - 30) // 10]
        sent = T0 + timedelta(days=i, hours=rng.randrange(0, 10), minutes=rng.randrange(60))
        zone = rng.choice((-8, -6, -5, 0, 1))
        hops = [sent + timedelta(seconds=rng.randrange(1, 6))]
        for _ in range(rng.choice((1, 2))):
            hops.append(hops[-1] + timedelta(seconds=rng.randrange(1, 9)))
        if kind == "ahead":
            sent += timedelta(minutes=rng.randrange(8, 40))
        elif kind == "disorder":
            hops[-1] = hops[0] - timedelta(minutes=rng.randrange(5, 30))
        elif kind == "slow":
            hops[-1] = hops[-2] + timedelta(minutes=rng.randrange(70, 110))
        local = sent.astimezone(timezone(timedelta(hours=zone)))
        received = [f"from a.example by b.example with ESMTPS id {i}; {format_datetime(h)}" for h in reversed(hops)]
        out.append((f"t{i}", timing.read(format_datetime(local), received), "fine" if kind == "ordinary" else "suspect"))
    return out


async def timing_learns(ada: Ada) -> dict[str, Any]:
    name = "check2c-timing"
    await make(ada, name, "timing")
    shape = steps.models()["timing"]["case"]
    cases = [(steps.fill(shape, {"timing": read, "id": mid}), answer, read["flags"]) for mid, read, answer in crafted()]
    ordinary, faulty = cases[:30], cases[30:]
    cut = {0: 7, 10: 7, 20: 6}  # of each fault's ten, how many are taught: 7 ahead, 7 out of order, 6 slow
    taught = ordinary[:20] + [c for at, n in cut.items() for c in faulty[at : at + n]]
    new = ordinary[20:] + [c for at, n in cut.items() for c in faulty[at + n : at + 10]]
    await hold(ada, name, [{"data": data, "outcome": answer} for data, answer, _ in taught])
    table: Counter[str] = Counter()
    unsure = 0
    for data, answer, _ in new:
        said = await ada("POST", f"/v1/models/{name}/decide", {"data": data})
        table[f"{answer}>{said.get('outcome') or 'no answer'}"] += 1
        unsure += bool(said.get("ask"))
    right = sum(n for k, n in table.items() if k.split(">")[0] == k.split(">")[1])
    return {"taught": len(taught), "asked": len(new), "as taught": right, "ada unsure": unsure,
            "answers": dict(sorted(table.items())),
            "flags of the crafted set": dict(Counter(f for _, _, fl in cases for f in fl))}  # fmt: skip
