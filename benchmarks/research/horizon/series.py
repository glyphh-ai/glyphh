"""The series the horizon benchmark reads, each a list of cases in time order: {"data", "ts", "outcomes"}, where a
case's outcomes say how things stood at its own time (today went up, today's move was big). What follows a case is
the case after it; nothing here is labelled with its future.

- aapl-daily, aapl-hourly: the two Ada Cloud models of those names, exported (data/<name>.zip, ada_export's jsonl).
  The export holds each case as the model stored it, every number as its bins; a case's data here is each number put
  back at the middle of its last bin, which the spec bins to the same situation.
- ring: a control whose answer is known. A Markov chain over 12 states with a fixed transition table, each state
  seen whole, so the best any reader can do at every lead is a number worked out from the table (ceiling())."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
DATA = HERE / "data"

# per market model: where a case's one-step return is, the move that counts as big (percent), and the returns over
# more steps whose bins have an edge at zero (so up or down is exact): {steps: role}
MARKETS = {
    "aapl-daily": {"layer": "day", "step": "ret_1d", "big": 2.0, "over": {5: "ret_5d", 20: "ret_20d", 60: "ret_60d"}},
    "aapl-hourly": {"layer": "bar", "step": "ret_1h", "big": 0.5, "over": {3: "ret_3h", 6: "ret_6h"}},
}


def _export(name: str) -> tuple[dict, list[dict]]:
    folder = DATA / name
    if not (folder / "precedents.jsonl").is_file():
        with zipfile.ZipFile(DATA / f"{name}.zip") as z:
            z.extractall(folder)
    spec = json.loads((folder / "spec.json").read_text())[-1]["spec"]
    rows = [json.loads(line) for line in open(folder / "precedents.jsonl")]
    rows.sort(key=lambda r: r["ts"])
    return spec, rows


def market(name: str) -> tuple[dict, list[dict]]:
    """(the spec, the cases) of one exported market model. The spec is the model's own layers with these outputs in
    place of its one: `dir` (the step's return: up, down), `size` (big when the step moved `big` percent or more,
    else calm) and `d<k>` (the return over the last k steps: up, down)."""
    cfg = MARKETS[name]
    spec, rows = _export(name)
    layer = cfg["layer"]
    numeric = {
        (seg["name"], role["name"]): role["numeric_config"]
        for seg in spec["layers"][0]["segments"]
        for role in seg["roles"]
        if "numeric_config" in role
    }
    outputs = {"dir": {"values": ["down", "up"]}, "size": {"values": ["big", "calm"]}}
    outputs.update({f"d{k}": {"values": ["down", "up"]} for k in cfg["over"]})
    spec = {"name": name, "layers": spec["layers"], "outputs": outputs}
    cases = []
    for row in rows:
        stored = row["situation"][layer]
        data: dict = {layer: {}}
        for seg, roles in stored.items():
            data[layer][seg] = {}
            for role, value in roles.items():
                c = numeric.get((seg, role))
                data[layer][seg][role] = min(float(value[-1]) + c["bin_width"] / 2, c["max_value"]) if c else value
        edge = float(stored["price"][cfg["step"]][-1])  # the bin [edge, edge + width) the step's return fell in
        outcomes = {
            "dir": "up" if edge >= 0 else "down",
            "size": "big" if edge >= cfg["big"] or edge < -cfg["big"] else "calm",
        }
        for k, role in cfg["over"].items():
            outcomes[f"d{k}"] = "up" if float(stored["price"][role][-1]) >= 0 else "down"
        cases.append({"data": data, "ts": row["ts"], "outcomes": outcomes, "stored": stored})
    return spec, cases


# -- baseball: a season's plate appearances, each game a thread --

BASEBALL_SPEC = {
    "name": "baseball",
    "seed": 7,
    "dimension": 2048,
    "layers": [
        {
            "name": "play",
            "segments": [
                {
                    "name": "state",
                    "roles": [
                        {"name": "outs"},
                        {"name": "bases"},
                        {"name": "inning"},
                        {"name": "half"},
                        {"name": "lead"},
                        {"name": "spot"},
                        {"name": "hands"},
                    ],
                },
                {
                    "name": "game",
                    "similarity_weight": 0,
                    "roles": [
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                        {"name": "n", "key_part": True, "similarity_weight": 0},
                    ],
                },
            ],
        }
    ],
    "outputs": {
        "reach": {"values": ["no", "yes"]},
        "run": {"values": ["no", "yes"]},
        "kind": {"values": ["out", "strikeout", "walk", "single", "extra", "homer", "other"]},
    },
}
BASEBALL_THREAD = "play.game.id"


def _kind(row: dict) -> str:
    if row["k"] == "1":
        return "strikeout"
    if row["hr"] == "1":
        return "homer"
    if row["double"] == "1" or row["triple"] == "1":
        return "extra"
    if row["single"] == "1":
        return "single"
    if row["walk"] == "1" or row["hbp"] == "1" or row["xi"] == "1":
        return "walk"
    if row["othout"] == "1" or row["fc"] == "1" or row["sh"] == "1" or row["sf"] == "1":
        return "out"
    return "other"


def _state(row: dict) -> dict:
    """The state a plate appearance starts from, as its row gives it."""
    inning = int(row["inning"])
    batting, fielding = (row["score_v"], row["score_h"]) if row["top_bot"] == "0" else (row["score_h"], row["score_v"])
    lead = int(batting or 0) - int(fielding or 0)
    return {
        "outs": f"{int(row['outs_pre'] or 0)} out",
        "bases": "".join("1" if row[b] else "-" for b in ("br1_pre", "br2_pre", "br3_pre")),
        "inning": "1-3" if inning <= 3 else "4-6" if inning <= 6 else "7-8" if inning <= 8 else "9+",
        "half": "top" if row["top_bot"] == "0" else "bottom",
        "lead": "behind 4+" if lead <= -4 else "behind" if lead < 0 else "tied" if lead == 0 else "ahead" if lead < 4 else "ahead 4+",
        "spot": f"bats {row['lp']}",
        "hands": "same" if row["bathand"] == row["pithand"] else "opposite",
    }


def baseball(games: int = 320, year: int = 2023) -> tuple[dict, list[dict]]:
    """(the spec, the cases) of a season's first `games` regular-season games, from Retrosheet's parsed plays
    (data/retrosheet/<year>plays.csv), in the order they were played. A case is one plate appearance just ended:
    its outcomes are what happened in it (the batter reached or not, a run scored or not, the kind of result), its
    situation the state the next plate appearance of the game starts from. So the next case's outcomes are what
    happens from here. A game's last plate appearance has no next state and is left out."""
    import csv

    by_game: dict[str, list[dict]] = {}
    with open(DATA / "retrosheet" / f"{year}plays.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["gametype"] == "regular" and row["pa"] == "1":
                by_game.setdefault(row["gid"], []).append(row)
    order = sorted(by_game, key=lambda g: (by_game[g][0]["date"], g))[:games]
    cases = []
    for gid in order:
        rows = by_game[gid]
        for n, (row, nxt) in enumerate(zip(rows, rows[1:])):
            kind = _kind(row)
            cases.append(
                {
                    "data": {"play": {"state": _state(nxt), "game": {"id": gid, "n": str(n)}}},
                    "ts": float(len(cases)),
                    "outcomes": {
                        "reach": "yes" if kind in ("walk", "single", "extra", "homer", "other") else "no",
                        "run": "yes" if int(row["runs"] or 0) > 0 else "no",
                        "kind": kind,
                    },
                    "thread": gid,
                }
            )
    return BASEBALL_SPEC, cases


# -- the control: a chain whose table is known --

STATES, ZONES = 12, 4


def table() -> np.ndarray:
    """The ring's transition table: from each state stay (0.55), step on one (0.30), jump on five (0.10), or land
    anywhere (0.05, evenly)."""
    t = np.full((STATES, STATES), 0.05 / STATES)
    for i in range(STATES):
        t[i, i] += 0.55
        t[i, (i + 1) % STATES] += 0.30
        t[i, (i + 5) % STATES] += 0.10
    return t


RING_SPEC = {
    "name": "ring",
    "seed": 11,
    "dimension": 2048,
    "layers": [{"name": "w", "segments": [{"name": "s", "roles": [{"name": "zone"}, {"name": "spot"}]}]}],
    "outputs": {"zone": {"values": [f"z{i}" for i in range(ZONES)]}},
}


def ring(n: int, seed: int = 1) -> tuple[dict, list[dict]]:
    """(the spec, n cases) of the ring: a state is its zone (state // 3) and its spot in it (state % 3), both seen;
    the output is the zone."""
    rng = np.random.default_rng(seed)
    t = table()
    state = int(rng.integers(STATES))
    cases = []
    for i in range(n):
        zone, spot = state // 3, state % 3
        cases.append(
            {
                "data": {"w": {"s": {"zone": f"z{zone}", "spot": f"s{spot}"}}},
                "ts": float(i),
                "outcomes": {"zone": f"z{zone}"},
                "state": state,
            }
        )
        state = int(rng.choice(STATES, p=t[state]))
    return RING_SPEC, cases


def ceiling(leads: list[int], back: bool = False) -> dict[int, dict[str, float]]:
    """What the ring allows at each lead, from its table alone: the best accuracy any reader of the present state
    can reach on the zone that many steps on (`back`: before), the accuracy of saying the zone stays as it is, and
    of always saying the commonest zone."""
    t = table()
    values, vectors = np.linalg.eig(t.T)
    pi = np.real(vectors[:, np.argmax(np.real(values))])
    pi = pi / pi.sum()
    zone = np.arange(STATES) // 3
    out = {}
    for k in leads:
        tk = np.linalg.matrix_power(t, k)
        if back:  # P(state k before = j | now = i) = pi_j T^k[j, i] / pi_i
            tk = (tk * pi[:, None]).T / pi[:, None]
        by_zone = np.stack([tk[:, zone == z].sum(axis=1) for z in range(ZONES)], axis=1)
        out[k] = {
            "best": float((pi * by_zone.max(axis=1)).sum()),
            "stays": float((pi * by_zone[np.arange(STATES), zone]).sum()),
            "commonest": float(max(pi[zone == z].sum() for z in range(ZONES))),
        }
    return out
