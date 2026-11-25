"""Two agents and a living glyphh: does a proposer and a skeptic who meet only in one Ada model trade better than
one LLM alone, or than the same two agents talking to each other?

    python agents.py              200 held-out hourly AAPL bars, after 100 warm-up bars
    python agents.py 200 100      (bars scored, warm-up bars)

Each agent is one fresh Claude (`claude -p`, as micro-gates runs its own): no tools, no settings, no session kept.

Every bar, an agent sees the bar as the hourly model stores it (returns, volume, hour, weekday; no ticker, no date,
so nothing it may remember of that day's market) and holds a position over the next bar: long, short or flat. A
position is paid the next bar's one-hour return, as its bin's middle (the export's bins are half a percent wide).

The arms, on the same bars:

- hold: always long.
- solo: one LLM, the proposer, with no memory.
- chat: the solo proposer's call, then a skeptic LLM who reads the call and its reason and approves, shrinks (half)
  or vetoes it. No memory.
- glyphh: the two never exchange a word. The proposer reads the ledger (one living Ada model: every call made so
  far in a situation like this one, and whether it paid), then calls. The call is a case in the ledger, and the
  ledger says how often calls like it paid: at FREE or more it goes through whole and the skeptic is not asked; at
  VETO or less it is dropped; between them, or on fewer than KNOWN precedents, the skeptic reads the case and its
  receipts (never the proposer's reason) and approves, shrinks or vetoes. When the next bar is in, the call is
  graded, vetoed or not (the market does not know), and recorded. The ledger starts empty and is warmed on the
  bars just before the scored ones (proposer only, nothing scored).

FREE, VETO and KNOWN were fixed before any scored bar was read. Every LLM answer is kept in results/agents-calls.jsonl
and read from there on a second run."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import run
import series

HERE = Path(__file__).parent
MODEL, EFFORT = "opus", "low"
BUDGET_USD, TIMEOUT = "1", 300  # the most one call may spend, and the seconds it may take
SERIES = "aapl-hourly"
FREE, VETO, KNOWN = 0.55, 0.45, 8  # the ledger's P(paid) for free rein and for a veto; the precedents either needs
SHOWN = 8  # receipts an agent reads
LEARN_EVERY = 25  # graded calls between the ledger's learns and calibrations
THESES = ["momentum", "reversion", "gap_follow", "gap_fade", "drift", "volume", "none"]
SIZE = {"approve": 1.0, "shrink": 0.5, "veto": 0.0}

BAR = (
    "One hourly bar of a large US stock, each number the middle of the bin it fell in: ret_1h, ret_3h, ret_6h, "
    "ret_24h, ret_5d and prev_day_ret are returns in percent up to this bar, from_open the percent since today's "
    "open, gap_open today's opening gap in percent, day_range_pos where the price sits in today's range (0 low, 100 "
    "high), vol_vs_hour this bar's volume against what is usual for its hour (1 is usual), vol_24h a 0-100 volume "
    "reading. A position is held for the next bar only and is paid that bar's return."
)
PROPOSER = (
    "You are the proposer of a trading desk. " + BAR + " Call long, short or flat for the next bar, name the one "
    "thesis the call stands on, and give the reason in one sentence. Flat is a real call: make it when nothing here "
    "says which way."
)
READS_LEDGER = (
    " You have a ledger: the calls made before now in the bars most like this one, the thesis each stood on, and "
    "whether it paid. It is the only memory you have; weigh it over your own priors, and little when it holds few."
)
SKEPTIC_CHAT = (
    "You are the skeptic of a trading desk. " + BAR + " The proposer has made a call for the next bar. Approve it "
    "(whole), shrink it (half) or veto it (flat), with the reason in one sentence."
)
SKEPTIC_LEDGER = (
    "You are the skeptic of a trading desk. " + BAR + " A call for the next bar is in the ledger, with the calls "
    "like it made before now and whether each paid, and how each thesis has paid so far. You do not hear the "
    "proposer's reasons, only what the ledger holds. Approve the call (whole), shrink it (half) or veto it (flat), "
    "with the reason in one sentence."
)
CALL = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["long", "short", "flat"]},
        "thesis": {"type": "string", "enum": THESES},
        "reason": {"type": "string"},
    },
    "required": ["action", "thesis", "reason"],
    "additionalProperties": False,
}
VERDICT = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": list(SIZE)}, "reason": {"type": "string"}},
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}

calls_path = HERE / "results" / "agents-calls.jsonl"
kept: dict[str, dict] = {}
lock = threading.Lock()
spent = {"usd": 0.0, "calls": 0}


def llm(key: str, system: str, user: str, schema: dict) -> dict:
    """One agent's answer, as the schema's JSON. Kept under `key` with what it was asked: asked again, it is read
    back, and a key whose question changed is an error rather than a stale answer."""
    if key in kept:
        if kept[key]["user"] != user or kept[key]["system"] != system:
            sys.exit(f"{key} was asked something else in {calls_path}; move that file away to run afresh")
        return kept[key]["answer"]
    answer, done = None, None
    for _ in range(3):  # a call that fails, or answers out of the schema's shape, is asked again
        with tempfile.TemporaryDirectory() as empty:
            done = subprocess.run(
                ["claude", "-p", "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
                 "--model", MODEL, "--effort", EFFORT, "--output-format", "json", "--max-budget-usd", BUDGET_USD,
                 "--json-schema", json.dumps(schema), "--system-prompt", system],
                input=user, capture_output=True, text=True, cwd=empty, timeout=TIMEOUT,
            )
        try:
            reply = json.loads(done.stdout)
        except json.JSONDecodeError:
            continue
        answer = reply.get("structured_output")
        if not reply.get("is_error") and isinstance(answer, dict) and set(schema["required"]) <= set(answer):
            break
        answer = None
    if answer is None:
        sys.exit(f"{key}: no answer in the schema's shape after three tries: {(done.stdout or done.stderr)[:300]}")
    with lock:
        kept[key] = {"key": key, "system": system, "user": user, "answer": answer}
        spent["usd"] += reply.get("total_cost_usd", 0)
        spent["calls"] += 1
        with open(calls_path, "a") as f:
            f.write(json.dumps(kept[key]) + "\n")
    return answer


def bar_text(case: dict) -> str:
    layer = next(iter(case["data"].values()))
    price = ", ".join(f"{k} {v:g}" for k, v in layer["price"].items())
    return f"{layer['clock']['weekday']} {layer['clock']['hour']}: {price}"


def ledger_spec(spec: dict) -> dict:
    """The hourly model's own bar, and beside it the call made on it; one output, whether the call paid."""
    layer = spec["layers"][0]
    call = {"name": "call", "roles": [{"name": "action"}, {"name": "thesis"}]}
    return {
        "name": "ledger",
        "layers": [{**layer, "segments": [*layer["segments"], call]}],
        "outputs": {"paid": {"values": ["lost", "won"]}},
    }


class Ledger:
    """The living glyphh: every graded call, and the words of each so a receipt can be read by an agent."""

    def __init__(self, spec: dict):
        self.model = run.glyphh_spec.Model(run.glyphh_spec.Spec.from_json(ledger_spec(spec)))
        self.layer = spec["layers"][0]["name"]
        self.text: dict[str, str] = {}
        self.theses: dict[str, list[int]] = {}  # thesis: [calls, paid]
        self.graded = 0

    def case(self, bar: dict, call: dict | None) -> dict:
        inner = dict(bar["data"][self.layer])
        if call:
            inner["call"] = {"action": call["action"], "thesis": call["thesis"]}
        return {self.layer: inner}

    def read(self, bar: dict, call: dict | None = None) -> dict:
        """What the ledger says of a bar (any call) or of a call on it: P(paid), how many precedents stand behind
        it, and the nearest of them in words."""
        if not self.graded:
            return {"p": None, "count": 0, "receipts": []}
        data = self.case(bar, call)
        answer = self.model.query(data, output="paid")
        p = self.model.probabilities(data, output="paid").get("won")
        receipts = [f"{sim:.2f} alike | {self.text[rid]}" for rid, sim, *_ in answer.receipts[:SHOWN] if rid in self.text]
        return {"p": p, "count": answer.count, "receipts": receipts}

    def grade(self, bar: dict, call: dict, move: float) -> None:
        paid = (move > 0) == (call["action"] == "long")
        rid = self.model.record(self.case(bar, call), ts=bar["ts"], outcomes={"paid": "won" if paid else "lost"})
        self.text[rid] = f"{bar_text(bar)} | {call['action']} on {call['thesis']} | next bar {move:+g}%: {'paid' if paid else 'lost'}"
        tally = self.theses.setdefault(call["thesis"], [0, 0])
        tally[0] += 1
        tally[1] += paid
        self.graded += 1
        if self.graded % LEARN_EVERY == 0:
            try:
                self.model.learn("paid")
                self.model.calibrate(output="paid")
            except run.glyphh_spec.SpecError:  # one outcome so far: nothing to learn yet
                pass

    def said(self, read: dict) -> str:
        if not read["receipts"]:
            return "The ledger holds nothing like this yet."
        head = f"The ledger: {read['count']} calls like this before now"
        head += f", paid {read['p']:.0%} of the time by its reckoning:" if read["p"] is not None else ":"
        return "\n".join([head, *("- " + r for r in read["receipts"])])

    def trust(self) -> str:
        if not self.theses:
            return ""
        parts = [f"{t} {won} of {n}" for t, (n, won) in sorted(self.theses.items())]
        return "How each thesis has paid so far: " + ", ".join(parts) + "."


def position(action: str, size: float = 1.0) -> float:
    return {"long": 1.0, "short": -1.0, "flat": 0.0}[action] * size


def summary(name: str, held: list[float], moves: list[float], against: dict[str, list[float]]) -> dict:
    pnl = [h * m for h, m in zip(held, moves)]
    on = [(h, m) for h, m in zip(held, moves) if h]
    row = {
        "arm": name,
        "bars": len(pnl),
        "total": sum(pnl),
        "in_market": len(on) / len(pnl),
        "right": sum((h > 0) == (m > 0) for h, m in on) / len(on) if on else None,
    }
    for other, theirs in against.items():
        diff, se = run.blocks([a - b for a, b in zip(pnl, theirs)], 20)
        row[f"vs_{other}"] = {"a_bar": diff, "se": se}
    return row


def main(scored: int = 200, warm: int = 100) -> None:
    spec, cases = series.market(SERIES)
    cut = int(len(cases) * run.LEARN)
    step = series.MARKETS[SERIES]["step"]
    layer = spec["layers"][0]["name"]
    move = lambda t: cases[t + 1]["data"][layer]["price"][step]  # noqa: E731  the next bar's return, its bin's middle
    bars = range(cut, cut + scored)
    moves = [move(t) for t in bars]
    calls_path.parent.mkdir(exist_ok=True)
    if calls_path.is_file():
        kept.update({r["key"]: r for r in map(json.loads, open(calls_path))})

    # solo, and chat on the solo call: no arm here reads another bar's answer, so the bars are asked side by side
    def solo(t: int) -> tuple[dict, dict | None]:
        call = llm(f"solo:{t}", PROPOSER, bar_text(cases[t]), CALL)
        if call["action"] == "flat":
            return call, None
        said = f"{bar_text(cases[t])}\nThe proposer's call: {call['action']} on {call['thesis']}. {call['reason']}"
        return call, llm(f"chat:{t}", SKEPTIC_CHAT, said, VERDICT)

    with ThreadPoolExecutor(8) as pool:
        answers = list(pool.map(solo, bars))
    held = {
        "hold": [1.0] * scored,
        "solo": [position(c["action"]) for c, _ in answers],
        "chat": [position(c["action"], SIZE[v["verdict"]] if v else 0.0) for c, v in answers],
    }
    print(f"  solo and chat done: {spent['calls']} calls", file=sys.stderr)

    # glyphh: one bar after another, each read after the bar before it was graded
    ledger = Ledger(spec)
    held["glyphh"], held["glyphh, the call alone"], paths = [], [], []
    for t in range(cut - warm, cut + scored):
        bar = cases[t]
        seen = ledger.read(bar)
        call = llm(f"glyphh:call:{t}", PROPOSER + READS_LEDGER, f"{bar_text(bar)}\n\n{ledger.said(seen)}", CALL)
        if t >= cut:
            size, path = 0.0, "flat"
            if call["action"] != "flat":
                of_call = ledger.read(bar, call)
                known = of_call["p"] is not None and of_call["count"] >= KNOWN
                if known and of_call["p"] >= FREE:
                    size, path = 1.0, "free"
                elif known and of_call["p"] <= VETO:
                    size, path = 0.0, "vetoed by the ledger"
                else:
                    asked = "\n\n".join(
                        p
                        for p in (
                            bar_text(bar),
                            f"The call: {call['action']} on {call['thesis']}.",
                            ledger.said(of_call),
                            ledger.trust(),
                        )
                        if p
                    )
                    verdict = llm(f"glyphh:skeptic:{t}", SKEPTIC_LEDGER, asked, VERDICT)["verdict"]
                    size, path = SIZE[verdict], f"skeptic: {verdict}"
            held["glyphh"].append(position(call["action"], size))
            held["glyphh, the call alone"].append(position(call["action"]))
            paths.append(path)
        if call["action"] != "flat":
            ledger.grade(bar, call, move(t))
        if (t - cut + warm + 1) % 50 == 0:
            print(f"  glyphh: bar {t - cut + warm + 1} of {warm + scored}, {ledger.graded} calls graded", file=sys.stderr)

    pnl = {name: [h * m for h, m in zip(hs, moves)] for name, hs in held.items()}
    rows = [
        summary(name, hs, moves, {o: pnl[o] for o in ("hold", "solo") if o != name}) for name, hs in held.items()
    ]
    counted = {p: paths.count(p) for p in sorted(set(paths))}
    out = {
        "series": SERIES,
        "model": MODEL,
        "effort": EFFORT,
        "scored": scored,
        "warm": warm,
        "from_case": cut,
        "free": FREE,
        "veto": VETO,
        "known": KNOWN,
        "arms": rows,
        "glyphh_paths": counted,
        "theses": ledger.theses,
        "spent_this_run": spent,
    }
    lines = [
        f"{SERIES}: {scored} held-out bars from case {cut}, the ledger warmed on the {warm} before; {MODEL}, effort {EFFORT}",
        f"{'arm':24}{'total %':>9}{'in market':>11}{'right':>8}{'vs hold, a bar':>17}{'± se':>8}{'vs solo, a bar':>17}{'± se':>8}",
    ]
    for r in rows:
        cell = lambda k: f"{r[k]['a_bar']:>+17.4f}{r[k]['se']:>8.4f}" if k in r else f"{'':>25}"  # noqa: E731
        right = f"{r['right']:>8.1%}" if r["right"] is not None else f"{'':>8}"
        lines.append(f"{r['arm']:24}{r['total']:>+9.2f}{r['in_market']:>11.0%}{right}{cell('vs_hold')}{cell('vs_solo')}")
    lines.append("the glyphh arm's calls went: " + ", ".join(f"{p} {n}" for p, n in counted.items()))
    lines.append("the theses in the ledger (calls, paid): " + ", ".join(f"{t} {n}/{w}" for t, (n, w) in sorted(ledger.theses.items())))
    (HERE / "results" / f"agents-{SERIES}.json").write_text(json.dumps(out, indent=1) + "\n")
    (HERE / "results" / f"agents-{SERIES}.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
