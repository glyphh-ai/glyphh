"""Shortlist recall and read latency on Postgres (kernel 3.12; Ada Cloud spec step 1).

A model in PostgresStore read the cloud's way (a worker holds no precedents): the `shortlist` nearest glyphs by
Hamming distance from pgvector's HNSW index, re-ranked by the kernel's exact weighted score; against the exact
read, every precedent scored. For each data set and shortlist size S:

  recall      the share of the exact top k (k = 15, the votes) found in the shortlist; ties at the k-th score
              count as found (any precedent scoring as high as the k-th is as good a vote)
  identical   the share of queries whose re-ranked top k scores are the exact top k scores, so the answer is the
              exact one
  decide      (credit, Banking77) the share of decide() answers identical to the exact read's, probabilities and all
  hamming     the same recall with an exact Hamming shortlist (a sequential scan): what the index costs
  latency     p50 and p99 of one decide() as a worker makes it: a fresh model on the store, nothing cached; exact
              reads load the whole partition each time

    python bench/shortlist.py --pg postgresql://... --data <rrotor>/benchmarks --what credit,banking77,synthetic

Data: credit and Banking77 as rrotor's benchmarks fetch them (benchmarks/credit/fetch.sh, banking77/fetch.sh);
the synthetic store is generated here (a support-ticket shape: categories, numbers and a short text).
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import random
import sys
import time
import uuid
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import glyphh_kernel as kernel  # noqa: E402
import glyphh_spec  # noqa: E402
import psycopg  # noqa: E402
from glyphh_postgres import PostgresStore  # noqa: E402

K = 15
OUT: dict = {}


def ms(xs: list[float], p: float) -> float:
    return round(float(np.percentile(xs, p)) * 1000, 1)


def with_settings(spec: glyphh_spec.Spec, **changes) -> glyphh_spec.Spec:
    return spec.with_settings(spec.settings.with_changes(changes))


def fresh(spec: glyphh_spec.Spec, store: PostgresStore) -> glyphh_spec.Model:
    """A worker's model: the spec and the store's learned meta, no precedent held."""
    return glyphh_spec.Model(spec, store=store)


# ── ground truth: the exact top of every query, by the kernel's own score ─────


def exact_tops(conn, schema: str, model: str, spec: glyphh_spec.Spec, queries: list[dict], keep: int, chunk: int = 25000):
    """Per query: (ids, scores) of the exact top `keep`, and the k-th score; scored chunk by chunk (a 1M store does
    not fit in one in-memory Space: 16 KB a precedent). A precedent's exact score does not depend on the others,
    so the chunks' tops merge into the store's."""
    learned = PostgresStore(conn, schema, model, dim=spec.dimension, readonly=True)
    m = glyphh_spec.Model(spec, store=learned)  # the store's learned tables, for the situations and weights
    asks = []
    for q in queries:
        situation = m.spec.situation(q)
        asks.append((situation, m.spec.weights(1.0, situation)))
    best = [([], np.array([])) for _ in queries]
    sel = learned._select().as_string(conn) + " ORDER BY seq"
    with conn.transaction(), conn.cursor(name=f"gt_{uuid.uuid4().hex[:8]}", binary=True) as cur:
        cur.itersize = chunk
        cur.execute(sel)
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            space = kernel.Space(dim=spec.dimension, seed=spec.seed, lexicon=m.settings.lexicon)
            for r in rows:
                rid, text, outcome, dim, glyph, author, ts, ev, _ = r
                space._append(rid, outcome, glyph.glyph(), author, ts, json.loads(text), None)
            for n, (situation, weights) in enumerate(asks):
                scores = space._fast_scores(situation, weights)
                top = np.argsort(scores, kind="stable")[::-1][:keep]
                ids = best[n][0] + [space._ids[i] for i in top]
                sc = np.concatenate([best[n][1], scores[top]])
                order = np.argsort(sc, kind="stable")[::-1][:keep]
                best[n] = ([ids[i] for i in order], sc[order])
    learned.close()
    return asks, best


def recall(store: PostgresStore, spec: glyphh_spec.Spec, asks, best, sizes: list[int], hamming_at: list[int], hamming_n: int):
    m = glyphh_spec.Model(spec, store=store)
    out = {}
    for size in sizes:
        for exact in (False, True):
            if exact and size not in hamming_at:
                continue
            found, identical, seconds = [], 0, []
            n_q = hamming_n if exact else len(asks)
            for (situation, weights), (ids, scores) in list(zip(asks, best))[:n_q]:
                glyph = m.space.encode(situation, None, weights)
                t0 = time.perf_counter()
                rows, _ = store.shortlist(glyph, size, exact=exact)
                seconds.append(time.perf_counter() - t0)
                listed = {r[0] for r in rows}
                kth = scores[K - 1]
                # every listed precedent's exact score: the top `keep` ones are known; the others score below them
                known = dict(zip(ids, scores))
                hits = sum(1 for rid in listed if rid in known and known[rid] >= kth - 1e-12)
                found.append(min(hits, K) / K)
                mine = sorted((known[rid] for rid in listed if rid in known), reverse=True)[:K]
                identical += len(mine) == K and np.allclose(mine, scores[:K], atol=1e-12)
            key = f"S={size}" + (" hamming" if exact else "")
            out[key] = {
                "recall": round(float(np.mean(found)), 4),
                "recall_min": round(float(np.min(found)), 4),
                "identical": round(identical / n_q, 4),
                "sql_p50_ms": ms(seconds, 50),
                "queries": n_q,
            }
            print(f"    {key:16s} recall {out[key]['recall']:.2%} (min {out[key]['recall_min']:.0%}), identical "
                  f"{out[key]['identical']:.1%}, the SQL p50 {out[key]['sql_p50_ms']} ms", flush=True)
    return out


def latency(conn, schema: str, model: str, spec: glyphh_spec.Spec, queries: list[dict], modes: dict[str, dict], n: int):
    out = {}
    for name, changes in modes.items():
        s = with_settings(spec, **changes)
        times = []
        for q in queries[:n]:
            store = PostgresStore(conn, schema, model, dim=spec.dimension)
            m = fresh(s, store)
            t0 = time.perf_counter()
            m.decide(q)
            times.append(time.perf_counter() - t0)
        out[name] = {"p50_ms": ms(times, 50), "p99_ms": ms(times, 99), "n": len(times)}
        print(f"    latency {name:22s} p50 {out[name]['p50_ms']} ms, p99 {out[name]['p99_ms']} ms (n {len(times)})", flush=True)
    return out


def agreement(conn, schema: str, model: str, spec: glyphh_spec.Spec, queries: list[dict], sizes: list[int]):
    ex_model = glyphh_spec.Model(spec, store=PostgresStore(conn, schema, model, dim=spec.dimension))
    ex_model.space.load()
    truth = [ex_model.decide(q) for q in queries]
    tops = [ex_model.query(q).top for q in queries]
    out = {}
    for size in sizes:
        m = glyphh_spec.Model(with_settings(spec, exact_below=0, shortlist=size), store=PostgresStore(conn, schema, model, dim=spec.dimension))
        got = [m.decide(q) for q in queries]
        same = sum(g == t for g, t in zip(got, truth))
        same_outcome = sum(g["outcome"] == t["outcome"] and g["ask"] == t["ask"] for g, t in zip(got, truth))
        drift = max(
            abs(g["probabilities"].get(o, 0.0) - t["probabilities"].get(o, 0.0))
            for g, t in zip(got, truth)
            for o in set(g["probabilities"]) | set(t["probabilities"])
        )
        same_top = sum(m.query(q).top == t for q, t in zip(queries, tops))
        n = len(queries)
        out[f"S={size}"] = {
            "decide_identical": round(same / n, 4),
            "outcome_and_ask_identical": round(same_outcome / n, 4),
            "max_probability_diff": round(drift, 4),
            "top_identical": round(same_top / n, 4),
        }
        print(f"    S={size:<6d} decide identical {same}/{n}, outcome and ask identical {same_outcome}/{n}, "
              f"largest probability change {drift:.4f}, query top identical {same_top}/{n}", flush=True)
    return out


def _module(path: Path, name: str):
    """One of rrotor's benchmark scripts, by its file (credit's and Banking77's are both run.py)."""
    import importlib.util

    sys.path.insert(0, str(path.parent))
    found = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(found)
    sys.modules[name] = module
    found.loader.exec_module(module)
    return module


# ── credit and Banking77 ─────────────────────────────────────────────


def credit(conn, schema: str, data: Path) -> None:
    sys.path.insert(0, str(data / "credit"))
    import calibrate  # noqa: E402  (rrotor's: the spec with costs, the data, the split)
    import run as base  # noqa: E402

    rows = base.load()
    random.Random(7).shuffle(rows)
    train, test = rows[:800], rows[800:]
    spec = calibrate.spec_with_costs().learned([(base.situation(c), c["decision"]) for c in train])
    spec = with_settings(spec, k=25, min_sim=0.25)
    store = PostgresStore(conn, schema, "credit", dim=spec.dimension)
    model = glyphh_spec.Model(spec, store=store)
    model.record_many([{"data": base.situation(c), "outcome": c["decision"]} for c in train])
    model.space.load()
    model.calibrate(sample=800)
    queries = [base.situation(c) for c in test]
    print(f"credit: {len(train)} precedents, {len(queries)} queries", flush=True)
    asks, best = exact_tops(conn, schema, "credit", spec, queries, keep=50)
    sizes = [25, 50, 100, 200, 400]
    OUT["credit"] = {
        "precedents": len(train),
        "recall": recall(store, spec, asks, best, sizes, [50, 100], len(queries)),
        "agreement": agreement(conn, schema, "credit", spec, queries, [100, 200, 400]),  # the setting's least is 100
        "latency": latency(conn, schema, "credit", spec, queries, {"exact (load all)": {"shortlist": 0}, "S=100": {"exact_below": 0, "shortlist": 100}}, 100),
    }


def banking77(conn, schema: str, data: Path) -> None:
    b77 = _module(data / "banking77" / "run.py", "b77_run")
    train, test = b77.load("train.csv"), b77.load("test.csv")
    spec = glyphh_spec.Spec.from_json(b77.SPEC)
    store = PostgresStore(conn, schema, "banking77", dim=spec.dimension)
    model = glyphh_spec.Model(spec, store=store)
    t0 = time.perf_counter()
    for start in range(0, len(train), 1000):
        model.record_many([{"data": {"message": {"body": {"text": t}}}, "outcome": label} for t, label in train[start : start + 1000]])
    imported = time.perf_counter() - t0
    model.space.load()
    t0 = time.perf_counter()
    model.learn()  # word weights and evidence; every glyph rewritten in the store
    learned = time.perf_counter() - t0
    print(f"banking77: {len(train)} recorded in {imported:.1f}s (record_many, batches of 1,000), learned in {learned:.1f}s", flush=True)
    sample = sorted(random.Random(7).sample(range(len(test)), 500))
    queries = [{"message": {"body": {"text": test[i][0]}}} for i in sample]
    truth = [test[i][1] for i in sample]
    asks, best = exact_tops(conn, schema, "banking77", spec, queries, keep=50)
    sizes = [100, 250, 500, 1000, 2000]
    agree = agreement(conn, schema, "banking77", spec, queries, sizes)
    ex = glyphh_spec.Model(spec, store=PostgresStore(conn, schema, "banking77", dim=spec.dimension))
    accuracy = {"exact": round(sum(ex.query(q).top == t for q, t in zip(queries, truth)) / len(queries), 4)}
    for size in sizes:
        m = glyphh_spec.Model(with_settings(spec, exact_below=0, shortlist=size), store=PostgresStore(conn, schema, "banking77", dim=spec.dimension))
        accuracy[f"S={size}"] = round(sum(m.query(q).top == t for q, t in zip(queries, truth)) / len(queries), 4)
    print(f"    accuracy on the 500: {accuracy}", flush=True)
    OUT["banking77"] = {
        "precedents": len(train),
        "import_s": round(imported, 1),
        "learn_s": round(learned, 1),
        "recall": recall(store, spec, asks, best, sizes, [500, 1000], 100),
        "agreement": agree,
        "accuracy": accuracy,
        "latency": latency(
            conn,
            schema,
            "banking77",
            spec,
            queries,
            {"exact (load all)": {"shortlist": 0}, "S=500": {"exact_below": 0, "shortlist": 500}, "S=1000": {"exact_below": 0, "shortlist": 1000}},
            60,
        ),
    }


# ── the synthetic store ──────────────────────────────────────────────

SYN = {
    "name": "tickets",
    "seed": 11,
    "dimension": 4096,
    "layers": [
        {
            "name": "case",
            "segments": [
                {"name": "who", "roles": [{"name": "plan"}, {"name": "region"}, {"name": "tier"}]},
                {
                    "name": "what",
                    "roles": [
                        {"name": "product"},
                        {"name": "component"},
                        {"name": "error"},
                        {"name": "severity", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                        {"name": "amount", "numeric_config": {"min_value": 0, "max_value": 10000, "bin_width": 500}},
                        {"name": "summary", "text_encoding": "bag_of_words"},
                    ],
                },
                {"name": "ref", "roles": [{"name": "id", "key_part": True, "similarity_weight": 0}]},
            ],
        }
    ],
}
OUTCOMES = [f"team_{i:02d}" for i in range(20)]
VOCAB = [f"w{i:03d}" for i in range(800)]


def syn_case(i: int, seed: int = 1) -> tuple[dict, str]:
    """A ticket: its team (the outcome) follows its product, its component's group and its words, with noise."""
    rng = random.Random(seed * 1_000_003 + i)
    product = rng.randrange(40)
    component = rng.randrange(300)
    team = (product * 7 + component // 30) % 20 if rng.random() > 0.15 else rng.randrange(20)
    words = rng.sample(VOCAB[team * 40 : team * 40 + 40], rng.randint(2, 4)) + rng.sample(VOCAB, rng.randint(1, 3))
    data = {
        "case": {
            "who": {"plan": rng.choice(["free", "pro", "team", "ent", "trial"]), "region": f"r{rng.randrange(12)}", "tier": rng.randrange(4)},
            "what": {
                "product": f"p{product}",
                "component": f"c{component}",
                "error": f"E{rng.randrange(2000)}",
                "severity": min(10, max(0, int(rng.gauss(team % 10, 2)))),
                "amount": rng.randrange(10000),
                "summary": " ".join(words),
            },
            "ref": {"id": f"t{seed}-{i}"},
        }
    }
    return data, OUTCOMES[team]


def syn_partial(data: dict) -> dict:
    """What a caller often knows first: the product, the severity and the words."""
    what = data["case"]["what"]
    return {"case": {"what": {"product": what["product"], "severity": what["severity"], "summary": what["summary"]}}}


def _load_range(args) -> int:
    pg, schema, model, start, end = args
    spec = glyphh_spec.Spec.from_json(SYN)
    with psycopg.connect(pg, autocommit=True) as conn:
        store = PostgresStore(conn, schema, model, dim=spec.dimension, index=False)
        m = glyphh_spec.Model(spec, store=store)
        for at in range(start, end, 1000):
            m.record_many([{"data": d, "outcome": o, "ts": float(i)} for i, (d, o) in ((j, syn_case(j)) for j in range(at, min(at + 1000, end)))])
    return end - start


def synthetic(conn, schema: str, pg: str, sizes: list[int], workers: int) -> None:
    spec = glyphh_spec.Spec.from_json(SYN)
    out = OUT.setdefault("synthetic", {})
    for n in sizes:
        model = f"syn_{n}"
        store = PostgresStore(conn, schema, model, dim=spec.dimension, index=False)
        store.drop_index()
        t0 = time.perf_counter()
        step = max(1000, -(-n // (workers * 4)) // 1000 * 1000)
        with mp.get_context("spawn").Pool(workers) as pool:
            done = sum(pool.map(_load_range, [(pg, schema, model, s, min(s + step, n)) for s in range(0, n, step)]))
        loaded = time.perf_counter() - t0
        conn.execute("SET max_parallel_maintenance_workers = 7")
        t0 = time.perf_counter()
        store.build_index()
        built = time.perf_counter() - t0
        conn.execute(f'ANALYZE "{schema}".precedents')
        size = conn.execute(
            "SELECT pg_total_relation_size(%s), pg_relation_size(%s)", (f'"{schema}".{store._t["part_name"].as_string(conn)}', f'"{schema}".{store._t["index"].as_string(conn)}')
        ).fetchone()
        print(f"synthetic {n}: {done} recorded in {loaded:.0f}s ({done / loaded:.0f}/s, {workers} workers), "
              f"HNSW built in {built:.0f}s, partition {size[0] / 2**20:.0f} MB of which index {size[1] / 2**20:.0f} MB", flush=True)
        full = [syn_case(i, seed=2)[0] for i in range(200)]
        partial = [syn_partial(q) for q in full]
        entry = {"precedents": done, "import_s": round(loaded, 1), "rows_per_s": round(done / loaded), "index_build_s": round(built, 1),
                 "partition_mb": round(size[0] / 2**20), "index_mb": round(size[1] / 2**20)}
        for kind, queries in (("full", full), ("partial", partial)):
            asks, best = exact_tops(conn, schema, model, spec, queries, keep=50)
            print(f"  {kind} queries:", flush=True)
            entry[f"recall_{kind}"] = recall(store, spec, asks, best, [250, 500, 1000, 2000], [1000] if n >= 100000 else [], 50)
        modes = {"S=500": {"exact_below": 0, "shortlist": 500}, "S=1000": {"exact_below": 0, "shortlist": 1000}, "S=2000": {"exact_below": 0, "shortlist": 2000}}
        if n <= 50000:
            modes = {"exact (load all)": {"shortlist": 0}, **modes}
        entry["latency"] = latency(conn, schema, model, spec, full, modes, 30 if n <= 50000 else 100)
        out[str(n)] = entry
        json.dump(OUT, open(HERE / "shortlist.json", "w"), indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg", required=True)
    ap.add_argument("--data", type=Path)
    ap.add_argument("--what", default="credit,banking77,synthetic")
    ap.add_argument("--sizes", default="5000,20000,50000,100000,1000000")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--schema", default=f"bench_{uuid.uuid4().hex[:8]}")
    ap.add_argument("--keep", action="store_true", help="keep the schema afterwards")
    args = ap.parse_args()
    conn = psycopg.connect(args.pg, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
    print(f"schema {args.schema}; pgvector {version}", flush=True)
    OUT["pgvector"] = version
    try:
        what = args.what.split(",")
        if "credit" in what:
            credit(conn, args.schema, args.data)
        if "banking77" in what:
            banking77(conn, args.schema, args.data)
        json.dump(OUT, open(HERE / "shortlist.json", "w"), indent=1)
        if "synthetic" in what:
            synthetic(conn, args.schema, args.pg, [int(s) for s in args.sizes.split(",")], args.workers)
    finally:
        json.dump(OUT, open(HERE / "shortlist.json", "w"), indent=1)
        if not args.keep:
            conn.execute(f'DROP SCHEMA IF EXISTS "{args.schema}" CASCADE')
        conn.close()


if __name__ == "__main__":
    main()
