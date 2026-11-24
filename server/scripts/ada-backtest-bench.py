"""The backtest against the benchmarks: German Credit and Banking77 (glyphh-ai/glyphh's benchmarks/; their fetch.sh
scripts get the data), each imported into a model with its held-out cases the newest, then backtested on those (the
benchmark's own hold-out) with the model's live settings, and with one candidate the benchmark also reports. The
numbers to reproduce are the benchmarks' READMEs:

- credit (calibrate.py): the learned spec with interactions, calibrated, decide: accuracy 70.0%, the bank's cost
  100; asking where every answer costs over 0.5, 111 of 200 decided at 81.1%; the plain vote 77.5%. Without the pairs
  (here: `interactions` off, so none is learned): decide 66.0%, cost 108.
- Banking77 (learned from its own store, word evidence 2): 88.2% of the 3,080; word evidence 0: 83.3%.

    GLYPHH_DATABASE_URL=postgresql+asyncpg://… python scripts/ada-backtest-bench.py --url http://server:8080 \\
        --host ada.load --code ../glyphh/benchmarks --data ../glyphh/benchmarks

--code is a checkout of glyphh-ai/glyphh's benchmarks/ (its credit/run.py reads the data and makes the split, as the
benchmark does);
--data holds credit/german.data and banking77/train.csv and test.csv. It makes a person straight in the database,
as scripts/ada-import.py does. Never against production.
"""

import argparse
import asyncio
import base64
import csv
import importlib.util
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
ada_import = importlib.import_module("ada-import")  # its signed_in: a person on Team


def _module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.parent.name + "_run", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def credit(code: Path, data: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """calibrate.py's spec (costs, ask 0.5, the segments' hand-set weights dropped) and settings (k 15, min_sim 0.35,
    calibrated on all 800), and run.py's split (seed 7: 800, then the 200 held out)."""
    run = _module(code / "credit" / "run.py")
    run.HERE = data / "credit"
    spec = json.loads(json.dumps(run.SPEC))
    spec["output"] = {"report": [], "costs": {"good": {"bad": 5.0}, "bad": {"good": 1.0}}, "ask": 0.5}
    for layer in spec["layers"]:
        for segment in layer["segments"]:
            segment.pop("similarity_weight", None)
    spec["settings"] = {"k": 15, "min_sim": 0.35, "calibrate_sample": 800}
    rows = run.load()
    random.Random(7).shuffle(rows)
    cases = [{"data": run.situation(c), "outcome": c["decision"], "ts": n} for n, c in enumerate(rows)]
    return spec, cases, [{"settings": {"interactions": False}, "name": "without the pairs"}]


def banking77(code: Path, data: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """run.py's spec, the set's own split: the 10,003 to learn from, then the 3,080 held out."""
    run = _module(code / "banking77" / "run.py")
    rows = []
    for name in ("train.csv", "test.csv"):
        with open(data / "banking77" / name, newline="") as f:
            rows += [(r["text"], r["category"]) for r in csv.DictReader(f)]
    cases = [{"data": {"message": {"body": {"text": t}}}, "outcome": c, "ts": n} for n, (t, c) in enumerate(rows)]
    return run.SPEC, cases, [{"settings": {"word_evidence": 0.0}, "name": "word evidence 0"}]


async def until_done(http: httpx.AsyncClient, key: dict[str, str], job: dict[str, Any]) -> dict[str, Any]:
    while job["state"] not in ("done", "failed"):
        await asyncio.sleep(2)
        job = (await http.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    return job


async def bench(http: httpx.AsyncClient, key: dict[str, str], name: str, made: tuple, held: int) -> dict[str, Any]:
    spec, cases, candidates = made
    (await http.post("/v1/models", json={"name": name, "spec": spec}, headers=key)).raise_for_status()
    content = base64.b64encode("".join(json.dumps(c) + "\n" for c in cases).encode()).decode()
    body = {"format": "jsonl", "content_base64": content, "learn": False}
    loaded = await until_done(http, key, (await http.post(f"/v1/models/{name}/imports", json=body, headers=key)).json())
    began = time.monotonic()
    asked = {"candidates": candidates, "holdout": {"newest": held}}
    job = await until_done(http, key, (await http.post(f"/v1/models/{name}/backtest", json=asked, headers=key)).json())
    out = {"model": name, "imported": loaded["result"]["recorded"], "seconds": round(time.monotonic() - began, 1)}
    for part in [job["result"]["active"], *job["result"]["candidates"]]:
        part.pop("mistakes", None)
    return {**out, **job["result"]}


async def main(args: argparse.Namespace) -> None:
    code, data = Path(args.code), Path(args.data)
    async with httpx.AsyncClient(base_url=args.url, headers={"host": args.host}, timeout=600) as http:
        made = await http.post("/v1/keys", json={"name": "bench"}, headers=await ada_import.signed_in())
        key = {"authorization": f"Bearer {made.json()['key']}"}
        print(json.dumps(await bench(http, key, "credit", credit(code, data), 200), indent=1), flush=True)
        print(json.dumps(await bench(http, key, "banking77", banking77(code, data), 3080), indent=1), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", default="ada.glyphh.ai")
    parser.add_argument("--code", required=True, help="the benchmarks/ directory (glyphh-ai/glyphh)")
    parser.add_argument("--data", required=True, help="where credit/german.data and banking77/*.csv are")
    asyncio.run(main(parser.parse_args()))
