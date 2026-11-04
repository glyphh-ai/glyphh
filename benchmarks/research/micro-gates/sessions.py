"""Does an agent with gates learn across sessions, where the same agent alone starts over? Ten sessions on one hidden
machine (world.py). Each brings new chains and new questions; at session CHANGE two actions change their rules, and
nobody is told. Every Claude call is a fresh process with no tools, no memory and no settings.

Four agents:
    cold   Claude alone, only this session's chains.
    notes  Claude with the notes it wrote itself last session, rewriting them each time.
    gates  the micro gates learn from the chains and answer what they can; Claude sees only the questions they refuse.
    beam   the same, read through the kernel's beam (3.17.0) instead of each gate's one best answer.

Seed 0 was the only world looked at while building, without Claude; the seed here ran once.

    uv run python sessions.py sim    # the gates alone on seed 0: no Claude
    uv run python sessions.py        # all three, into results/sessions.json and results/sessions.txt
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import gates
import world

HERE = Path(__file__).parent
SEED, DEV_SEED = 11, 0
SESSIONS, CHANGE, CHANGED_ACTIONS = 10, 6, 2
CHAINS_PER_SESSION = 30  # too few to solve a session alone: only what was kept can answer
QUESTIONS = (3, 3, 3, 3, 5, 5, 5, 5, 8, 8, 8, 8, 12, 12, 12, 12, 16, 16, 16, 16)
DAY = 86_400.0
GATES = {"gates": (gates.Gates, DAY), "beam": (gates.BeamGates, DAY / 2)}  # each agent's best fade on seed 0
AGENTS = ("cold", "notes", "gates", "beam")
BUDGET_USD = "6"  # the most one Claude call may spend
TIMEOUT = 900
RULES = (
    "A hidden machine has states and actions, all with made-up names. Each action moves every state to one state.\n"
    "Each line is a start state, a list of actions applied in order, and the state it ended in. About 5% of the lines "
    "record a wrong end. The machine's rules can change between sessions, without warning.\n"
)
ANSWERS = "Reply with one line per question, the number, a space, the state, inside <answers></answers>. Guess if you must."


@dataclass(frozen=True)
class Session:
    number: int
    chains: tuple[world.Chain, ...]
    questions: tuple[world.Chain, ...]


def walk(moves: dict, start: str, actions: tuple[str, ...]) -> str:
    for action in actions:
        start = moves[start, action]
    return start


def sessions(seed: int) -> tuple[list[Session], world.World]:
    w = world.make(seed)
    rng = random.Random(seed * 1000 + 1)
    moves, out = dict(w.moves), []
    for number in range(1, SESSIONS + 1):
        if number == CHANGE:
            for action in rng.sample(w.actions, CHANGED_ACTIONS):
                moves.update({(s, action): t for s, t in zip(w.states, rng.sample(w.states, len(w.states)))})
        chains = []
        for _ in range(CHAINS_PER_SESSION):
            start, chain = rng.choice(w.states), tuple(rng.choices(w.actions, k=rng.choice((1, 2, 3))))
            end = walk(moves, start, chain)
            if rng.random() < world.NOISE:
                end = rng.choice([s for s in w.states if s != end])
            chains.append(world.Chain(start, chain, end))
        questions = []
        for length in QUESTIONS:
            start, chain = rng.choice(w.states), tuple(rng.choices(w.actions, k=length))
            questions.append(world.Chain(start, chain, walk(moves, start, chain)))
        out.append(Session(number, tuple(chains), tuple(questions)))
    return out, w


def lines(chains) -> str:
    return "\n".join(f"{c.start} {' '.join(c.actions)} -> {c.end}" for c in chains)


def asked(questions) -> str:
    return "\n".join(f"{i} {c.start} {' '.join(c.actions)}" for i, c in enumerate(questions, 1))


def claude(prompt: str) -> dict:
    """One fresh Claude: no tools, no MCP servers, no settings, no session kept."""
    began = time.time()
    with tempfile.TemporaryDirectory() as empty:
        done = subprocess.run(
            ["claude", "-p", "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
             "--model", "opus", "--output-format", "json", "--max-budget-usd", BUDGET_USD,
             "--system-prompt", "Do the task exactly as asked. Reason it through as far as you need."],
            input=prompt, capture_output=True, text=True, cwd=empty, timeout=TIMEOUT,
        )
    try:
        reply = json.loads(done.stdout)
    except json.JSONDecodeError:
        reply = {"result": "", "is_error": True}
    usage = reply.get("usage", {})
    tokens = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
    return {
        "text": reply.get("result") or "",
        "error": bool(reply.get("is_error")),
        "tokens": tokens,
        "usd": reply.get("total_cost_usd", 0),
        "seconds": time.time() - began,
    }


def parsed(text: str) -> dict[int, str]:
    block = re.search(r"<answers>(.*?)</answers>", text, re.S)
    return {int(n): s for n, s in re.findall(r"^\s*(\d+)\s+(\w+)\s*$", block.group(1) if block else "", re.M)}


def scored(number: int, agent: str, right: int, call: dict | None, **more) -> dict:
    call = call or {"tokens": 0, "usd": 0, "seconds": 0, "error": False}
    return {"session": number, "agent": agent, "right": right, "of": len(QUESTIONS)} | {k: call[k] for k in ("tokens", "usd", "seconds", "error")} | more


def cold(s: Session) -> dict:
    call = claude(f"{RULES}\n{lines(s.chains)}\n\nQuestions:\n{asked(s.questions)}\n\n{ANSWERS}")
    answers = parsed(call["text"])
    return scored(s.number, "cold", sum(answers.get(i) == q.end for i, q in enumerate(s.questions, 1)), call)


def notes_run(all_sessions: list[Session]) -> list[dict]:
    notes, rows = "(none yet: this is your first session)", []
    for s in all_sessions:
        call = claude(
            f"{RULES}\nYour notes from earlier sessions:\n<notes>\n{notes}\n</notes>\n\nThis session's lines:\n{lines(s.chains)}\n\n"
            f"Questions:\n{asked(s.questions)}\n\n{ANSWERS}\nThen rewrite your notes inside <notes></notes>: they are all you "
            "will have next session, so keep whatever will help you then."
        )
        answers = parsed(call["text"])
        kept = re.search(r"<notes>(.*?)</notes>", call["text"], re.S)
        notes = kept.group(1).strip() if kept else notes
        right = sum(answers.get(i) == q.end for i, q in enumerate(s.questions, 1))
        rows.append(scored(s.number, "notes", right, call, notes_chars=len(notes)))
    (HERE / "results/sessions_notes.txt").write_text(notes + "\n")
    return rows


def gates_session(g: gates.Gates, s: Session, rng: random.Random) -> tuple[int, list[world.Chain], float]:
    began = time.time()
    g.now = s.number * DAY
    g.train(list(s.chains), rng)
    right, refused = 0, []
    for q in s.questions:
        answer = g.run(q.start, q.actions)
        if answer is None:
            refused.append(q)
        else:
            right += answer == q.end
    return right, refused, time.time() - began


def gates_run(all_sessions: list[Session], w: world.World, agent: str) -> list[dict]:
    kind, half_life = GATES[agent]
    g, rng, rows = kind(w.actions, w.states, half_life), random.Random(SEED), []
    for s in all_sessions:
        right, refused, seconds = gates_session(g, s, rng)
        call = None
        if refused:
            call = claude(f"{RULES}\n{lines(s.chains)}\n\nQuestions:\n{asked(refused)}\n\n{ANSWERS}")
            answers = parsed(call["text"])
            right += sum(answers.get(i) == q.end for i, q in enumerate(refused, 1))
        row = scored(s.number, agent, right, call, refused=len(refused), gate_seconds=seconds)
        rows.append(row)
    return rows


def sim() -> None:
    all_sessions, w = sessions(DEV_SEED)
    for agent, (kind, half_life) in GATES.items():
        g, rng = kind(w.actions, w.states, half_life), random.Random(DEV_SEED)
        for s in all_sessions:
            right, refused, seconds = gates_session(g, s, rng)
            print(f"{agent} session {s.number:>2}: right {right} of {len(s.questions)}, refused {len(refused)}, {seconds:.1f}s")


def table(rows: list[dict]) -> str:
    out = [f"One hidden world, {SESSIONS} sessions, {len(QUESTIONS)} questions each. The rules change at session {CHANGE}.", ""]
    out += ["session  " + "".join(f"{a + ' right':>13}{'tokens':>9}{'sec':>6}" for a in AGENTS)]
    for number in range(1, SESSIONS + 1):
        cells = ""
        for agent in AGENTS:
            r = next(x for x in rows if x["agent"] == agent and x["session"] == number)
            cells += f"{r['right']:>13}{r['tokens']:>9}{r['seconds']:>6.0f}"
        out.append(f"{number:<9}{cells}")
    totals = {a: [r for r in rows if r["agent"] == a] for a in AGENTS}
    out += [""] + [
        f"{a}: {sum(r['right'] for r in rs)} of {sum(r['of'] for r in rs)} right, {sum(r['tokens'] for r in rs):,} tokens, "
        f"${sum(r['usd'] for r in rs):.2f}, {sum(r['error'] for r in rs)} failed calls"
        for a, rs in totals.items()
    ]
    return "\n".join(out)


def main() -> None:
    if sys.argv[1:] == ["sim"]:
        return sim()
    all_sessions, w = sessions(SEED)
    with ThreadPoolExecutor(5) as pool:
        cold_rows = pool.map(cold, all_sessions)
        notes_rows = pool.submit(notes_run, all_sessions)
        gates_rows = [pool.submit(gates_run, all_sessions, w, agent) for agent in GATES]
        rows = list(cold_rows) + notes_rows.result() + [row for future in gates_rows for row in future.result()]
    (HERE / "results/sessions.json").write_text(json.dumps(rows, indent=1) + "\n")
    text = table(rows)
    (HERE / "results/sessions.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
