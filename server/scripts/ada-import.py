"""An import at scale, end to end: a JSON Lines file of `--rows` cases sent to its upload link, imported as a job (the
whole file checked against the plan's cap, the index dropped, recorded a thousand a transaction, learned once, the
index built), then asked.

    GLYPHH_DATABASE_URL=postgresql+asyncpg://… python scripts/ada-import.py --url http://server:8080 --host ada.load \\
        --rows 1000000

It makes a person (on Team, whose cap is a million) straight in the database, as scripts/ada-load.py does, a key and a
model through the API, writes the file once (kept beside the script's --file for the next run), and prints the
upload's time, the job's own (checked, recorded, total) and wall time, its result, and the reads' latency after. Run it
against a server and its workers on a private network; never against production.
"""

import argparse
import asyncio
import json
import os
import random
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import insert, select, update

from glyphh_server.config import get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.models import Install, Org, Plan, PlanVersion, User
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.orgs import new_person

SPEC: dict[str, Any] = {
    "name": "orders",
    "layers": [
        {
            "name": "o",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "product"},
                        {"name": "channel"},
                        {"name": "region"},
                        {"name": "size", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
}


def row(rng: random.Random, i: int) -> str:
    product, channel, region, size = rng.choice("abcdefgh"), rng.choice("mcp"), rng.choice("uea"), rng.randint(0, 10)
    fraud = (product in "abc") ^ (size > 7) ^ (rng.random() < 0.1)
    data = {"o": {"s": {"product": product, "channel": channel, "region": region, "size": size, "id": i}}}
    return json.dumps({"data": data, "outcome": "fraud" if fraud else "ok"}, separators=(",", ":")) + "\n"


def write(path: str, rows: int) -> None:
    if os.path.exists(path):
        return
    rng = random.Random(7)
    with open(path, "w") as out:
        for i in range(rows):
            out.write(row(rng, i))


async def signed_in() -> dict[str, str]:
    """A new person signed in, their org on Team (a million precedents)."""
    engine = make_engine(get_settings().database_url)
    async with engine.begin() as conn:
        user_id = await new_person(conn, f"import-{uuid.uuid4().hex[:8]}@load.test", "Import Test")
        values = {"user_id": user_id, "machine_id": uuid.uuid4().hex, "name": "import", "surface": "desktop"}
        made = insert(Install).values(**values, mod_version="1.0.0").returning(Install.id)
        install_id = (await conn.execute(made)).scalar_one()
        token = await tokens.issue(conn, install_id)
        team = select(PlanVersion.id).join(Plan).where(Plan.name == "Team").order_by(PlanVersion.version.desc())
        version = (await conn.execute(team.limit(1))).scalar_one()
        org = select(User.org_id).where(User.id == user_id).scalar_subquery()
        await conn.execute(update(Org).values(plan_version_id=version).where(Org.id == org))
    await engine.dispose()
    return {"authorization": f"Bearer {token}"}


async def stream(path: str) -> Any:
    with open(path, "rb") as source:
        while piece := source.read(1 << 20):
            yield piece


async def main(args: argparse.Namespace) -> None:
    write(args.file, args.rows)
    async with httpx.AsyncClient(base_url=args.url, headers={"host": args.host}, timeout=3600) as http:
        person = await signed_in()
        made = await http.post("/v1/keys", json={"name": "import"}, headers=person)
        key = {"authorization": f"Bearer {made.json()['key']}"}
        name = f"imp-{uuid.uuid4().hex[:8]}"
        (await http.post("/v1/models", json={"name": name, "spec": SPEC}, headers=key)).raise_for_status()
        began = time.monotonic()
        job = (await http.post(f"/v1/models/{name}/imports", json={"format": "jsonl"}, headers=key)).json()
        path = "/" + job["upload"]["url"].split("://", 1)[1].split("/", 1)[1]
        (await http.put(path, content=stream(args.file))).raise_for_status()
        uploaded = time.monotonic() - began
        while job["state"] not in ("done", "failed"):
            await asyncio.sleep(5)
            job = (await http.get(f"/v1/jobs/{job['id']}", headers=key)).json()
            print(json.dumps({"at": round(time.monotonic() - began), "state": job["state"], "percent": job["percent"]}))
        took = time.monotonic() - began
        rng, seen = random.Random(), []
        for _ in range(50):
            data = json.loads(row(rng, rng.randrange(10**9)))["data"]
            started = time.perf_counter()
            (await http.post("/v1/decide", json={"model": name, "data": data}, headers=key)).raise_for_status()
            seen.append(1000 * (time.perf_counter() - started))
        seen.sort()
        timing = {"rows": args.rows, "upload_s": round(uploaded, 1), "wall_s": round(took, 1)}
        timing |= {"decide_p50_ms": round(seen[25], 1), "decide_p95_ms": round(seen[47], 1)}
        print(json.dumps({**timing, "state": job["state"], "result": job.get("result"), "error": job.get("error")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", default="ada.glyphh.ai")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--file", default="/tmp/ada-import.jsonl")
    asyncio.run(main(parser.parse_args()))
