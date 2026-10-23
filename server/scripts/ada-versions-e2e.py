"""Ada versions end to end (docs/specs/ada-cloud.md, 12.10): a server with two kernels installed, ada-1-0 (3.12.2, the
venv's) and ada-1-1-beta (3.13.0, in /opt/ada/3.13.0), each served by worker processes that imported only their own
copy. On German Credit (rrotor's benchmarks/credit; 800 learned, 200 held out, as its calibrate.py), one model:

1. made on ada-1-0, its 800 cases recorded, learned and calibrated; the 200 decided (the "before" answers);
2. a model made on ada-1-1-beta beside it: both answer at once, each on its own kernel;
3. a backtest of the active version against ada-1-1-beta on the model's own held-out precedents (its newest 200 of
   the 800);
4. the upgrade to ada-1-1-beta: a re-encode job on the beta's kernel; the 200 decided again (they differ where a
   query's pair value was never learned: the beta's change);
5. the rollback to version 1, on its own kernel: the 200 answered exactly as before the upgrade.

    GLYPHH_DATABASE_URL=postgresql+asyncpg://… python scripts/ada-versions-e2e.py --url http://server:8080 \\
        --host ada.e2e --code ../rrotor/benchmarks --data ../rrotor/benchmarks

It makes a person straight in the database, as scripts/ada-import.py does. Never against production."""

import argparse
import asyncio
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
ada_import = importlib.import_module("ada-import")
bench = importlib.import_module("ada-backtest-bench")
BETA = "ada-1-1-beta"


async def job_done(http: httpx.AsyncClient, key: dict[str, str], job: dict[str, Any]) -> dict[str, Any]:
    while job["state"] not in ("done", "failed"):
        await asyncio.sleep(0.5)
        job = (await http.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    assert job["state"] == "done", job
    return job


async def decide_all(http: httpx.AsyncClient, key: dict[str, str], name: str, held: list[dict[str, Any]]) -> list[Any]:
    out = []
    for case in held:
        got = await http.post(f"/v1/models/{name}/decide", json={"data": case["data"]}, headers=key)
        got.raise_for_status()
        answer = got.json()
        out.append(
            (answer["outcome"], {k: round(v, 6) for k, v in answer["probabilities"].items()}, got.headers["glyphh-ada"])
        )
    return out


async def main(args: argparse.Namespace) -> dict[str, Any]:
    spec, cases, _ = bench.credit(Path(args.code), Path(args.data))
    train, held = cases[:800], cases[800:]
    report: dict[str, Any] = {}
    async with httpx.AsyncClient(base_url=args.url, headers={"host": args.host}, timeout=600) as http:
        person = await ada_import.signed_in()
        made = (await http.post("/v1/keys", json={"name": "e2e"}, headers=person)).json()
        key = {"authorization": f"Bearer {made['key']}"}
        listed = (await http.get("/v1/ada", headers=key)).json()
        report["versions"] = [(v["name"], v["kernel"], v["status"]) for v in listed["versions"]]
        for name, ada in (("credit", "ada-1-0"), ("credit-beta", BETA)):
            made = await http.post("/v1/models", json={"name": name, "spec": spec, "ada": ada}, headers=key)
            assert made.status_code == 201, made.text
            for at in range(0, 800, 400):
                got = await http.post(
                    f"/v1/models/{name}/record_many", json={"cases": train[at : at + 400]}, headers=key
                )
                got.raise_for_status()
            await job_done(http, key, (await http.post(f"/v1/models/{name}/learn", headers=key)).json())
        before = await decide_all(http, key, "credit", held)
        beside = await decide_all(http, key, "credit-beta", held)
        report["side_by_side"] = {
            "ada-1-0 answered by": sorted({a[2] for a in before}),
            "beta answered by": sorted({a[2] for a in beside}),
            "decisions that differ": sum(a[0] != b[0] for a, b in zip(before, beside, strict=True)),
            "probabilities that differ": sum(a[1] != b[1] for a, b in zip(before, beside, strict=True)),
        }
        began = time.monotonic()  # the backtest holds out the model's own newest 200 of its 800 and learns from 600
        body = {"ada": BETA, "holdout": {"newest": 200}}
        tried = await job_done(
            http, key, (await http.post("/v1/models/credit/backtest", json=body, headers=key)).json()
        )
        result = tried["result"]
        keep = ("accuracy", "top_accuracy", "cost_mean", "log_loss", "ask_rate")
        report["backtest"] = {
            "seconds": round(time.monotonic() - began, 1),
            "active": {k: result["active"].get(k) for k in ("ada", *keep)},
            "beta": {k: result["candidates"][0].get(k) for k in ("ada", *keep)},
            "change": result["candidates"][0].get("change"),
        }
        began = time.monotonic()
        up = (
            await http.post("/v1/models/credit/upgrade", json={"ada": BETA, "backtest": tried["id"]}, headers=key)
        ).json()
        await job_done(http, key, up["job"])
        report["upgrade"] = {
            "seconds": round(time.monotonic() - began, 1),
            "version": up["version"],
            "from": up["from"],
        }
        upgraded = await decide_all(http, key, "credit", held)
        versions = (await http.get("/v1/models/credit/versions", headers=key)).json()["versions"]
        report["versions_of_credit"] = [(v["version"], v["ada"], v["kernel"], v["active"]) for v in versions]
        began = time.monotonic()
        back = (await http.post("/v1/models/credit/versions/1/activate", headers=key)).json()
        await job_done(http, key, back["job"])
        rolled = await decide_all(http, key, "credit", held)
        report["upgraded_answered_by"] = sorted({a[2] for a in upgraded})
        report["upgraded_vs_before_decisions_differ"] = sum(a[0] != b[0] for a, b in zip(before, upgraded, strict=True))
        report["rollback"] = {
            "seconds": round(time.monotonic() - began, 1),
            "answered_by": sorted({a[2] for a in rolled}),
            "decisions_as_before": sum(a[0] == b[0] for a, b in zip(before, rolled, strict=True)),
            "probabilities_as_before": sum(a[1] == b[1] for a, b in zip(before, rolled, strict=True)),
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", default="ada.glyphh.ai")
    parser.add_argument("--code", required=True, help="rrotor's benchmarks/ directory")
    parser.add_argument("--data", required=True, help="where credit/german.data is")
    print(json.dumps(asyncio.run(main(parser.parse_args())), indent=2))
