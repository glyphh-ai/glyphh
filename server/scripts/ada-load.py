"""Load on Ada Cloud: reads a second and their latency through the whole path (the API at its Ada host, Redis, the
worker processes, Postgres with pgvector), on many models at once.

    GLYPHH_DATABASE_URL=postgresql+asyncpg://… python scripts/ada-load.py --url http://server:8080 --host ada.load \\
        --models 100 --precedents 1000 --concurrency 64 --seconds 60

It makes a person and an org straight in the database (as the tests' helpers do), an API key through the API, then
`--models` models of one spec, each loaded with `--precedents` graded cases by record_many (1,000 a call), then sends
POST /v1/decide for `--seconds` from `--concurrency` callers at once, each a random model and a random case, and prints
reads a second, the latency's p50, p95 and p99, and every refusal by its code. Run it against a server and its workers
on a private network; never against production.
"""

import argparse
import asyncio
import json
import random
import statistics
import time
import uuid
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import insert

from glyphh_server.config import get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.models import Install
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.orgs import new_person

SPEC: dict[str, Any] = {
    "name": "tickets",
    "layers": [
        {
            "name": "ticket",
            "segments": [
                {
                    "name": "what",
                    "roles": [
                        {"name": "product"},
                        {"name": "channel"},
                        {"name": "plan"},
                        {"name": "region"},
                        {"name": "age_days", "numeric_config": {"min_value": 0, "max_value": 30, "bin_width": 3}},
                        {"name": "text", "text_encoding": "bag_of_words"},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "output": {"costs": {"refund": {"keep": 3}, "keep": {"refund": 1}}, "ask_below": 0.6},
}
WORDS = [
    "card",
    "lost",
    "charge",
    "twice",
    "refund",
    "late",
    "broken",
    "login",
    "password",
    "slow",
    "app",
    "crash",
    "invoice",
    "wrong",
]


def case(rng: random.Random, i: int) -> dict[str, Any]:
    product, channel = rng.choice("abcdefgh"), rng.choice(["mail", "chat", "phone"])
    plan, region, age = rng.choice(["free", "pro", "team"]), rng.choice(["us", "eu", "ap"]), rng.randint(0, 30)
    text = " ".join(rng.sample(WORDS, 4))
    refund = (product in "abc") ^ (age > 20) ^ ("twice" in text) ^ (rng.random() < 0.1)
    what = {"product": product, "channel": channel, "plan": plan, "region": region, "age_days": age, "text": text}
    return {"data": {"ticket": {"what": {**what, "id": f"t{i}"}}}, "outcome": "refund" if refund else "keep"}


async def signed_in() -> dict[str, str]:
    engine = make_engine(get_settings().database_url)
    async with engine.begin() as conn:
        user_id = await new_person(conn, f"load-{uuid.uuid4().hex[:8]}@load.test", "Load Test")
        values = {"user_id": user_id, "machine_id": uuid.uuid4().hex, "name": "load", "surface": "desktop"}
        values["mod_version"] = "1.0.0"
        install_id = (await conn.execute(insert(Install).values(values).returning(Install.id))).scalar_one()
        token = await tokens.issue(conn, install_id)
    await engine.dispose()
    return {"authorization": f"Bearer {token}"}


async def load(http: httpx.AsyncClient, key: dict[str, str], name: str, precedents: int, seed: int) -> None:
    made = await http.post("/v1/models", json={"name": name, "spec": SPEC}, headers=key)
    made.raise_for_status()
    rng = random.Random(seed)
    for start in range(0, precedents, 1000):
        cases = [case(rng, i) for i in range(start, min(start + 1000, precedents))]
        done = await http.post(f"/v1/models/{name}/record_many", json={"cases": cases}, headers=key, timeout=120)
        done.raise_for_status()


async def caller(http: httpx.AsyncClient, key: dict, models: int, until: float, seen: list, codes: Counter) -> None:
    rng = random.Random()
    while time.monotonic() < until:
        body = {"model": f"m{rng.randrange(models)}", "data": case(rng, rng.randrange(10**9))["data"]}
        started = time.perf_counter()
        got = await http.post("/v1/decide", json=body, headers=key)
        seen.append(time.perf_counter() - started)
        codes[got.json()["error"]["code"] if got.status_code >= 400 else got.status_code] += 1


def report(seen: list[float], codes: Counter, seconds: float, args: argparse.Namespace) -> dict[str, Any]:
    ms = sorted(x * 1000 for x in seen)
    at = lambda p: round(ms[min(len(ms) - 1, int(p * len(ms)))], 1)  # noqa: E731
    return {
        "models": args.models,
        "precedents_each": args.precedents,
        "concurrency": args.concurrency,
        "seconds": round(seconds, 1),
        "reads": len(ms),
        "reads_per_second": round(len(ms) / seconds, 1),
        "p50_ms": at(0.50),
        "p95_ms": at(0.95),
        "p99_ms": at(0.99),
        "mean_ms": round(statistics.fmean(ms), 1),
        "answers": dict(codes),
    }


async def main(args: argparse.Namespace) -> None:
    limits = httpx.Limits(max_connections=args.concurrency + 8, max_keepalive_connections=args.concurrency + 8)
    async with httpx.AsyncClient(base_url=args.url, headers={"host": args.host}, timeout=60, limits=limits) as http:
        if args.key:  # the models a run before made, asked again
            key = {"authorization": f"Bearer {args.key}"}
        else:
            made = await http.post("/v1/keys", json={"name": "load"}, headers=await signed_in())
            key = {"authorization": f"Bearer {made.json()['key']}"}
            started = time.monotonic()
            for batch in range(0, args.models, 8):
                names = range(batch, min(batch + 8, args.models))
                await asyncio.gather(*(load(http, key, f"m{n}", args.precedents, n) for n in names))
            print(json.dumps({"loaded_seconds": round(time.monotonic() - started, 1), "key": made.json()["key"]}))
        await http.post("/v1/decide", json={"model": "m0", "data": case(random.Random(), 0)["data"]}, headers=key)
        seen: list[float] = []
        codes: Counter = Counter()
        until = time.monotonic() + args.seconds
        began = time.monotonic()
        await asyncio.gather(*(caller(http, key, args.models, until, seen, codes) for _ in range(args.concurrency)))
        print(json.dumps(report(seen, codes, time.monotonic() - began, args)), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", default="ada.glyphh.ai")
    parser.add_argument("--models", type=int, default=100)
    parser.add_argument("--precedents", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--key", default="", help="An API key of a run before: its models asked, nothing made")
    asyncio.run(main(parser.parse_args()))
