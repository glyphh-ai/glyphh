"""Kubernetes issues as an Ada model, graded on the weeks it never saw.

Builds the memory through the Ada plugin's MCP server (the real one,
GLYPHH_HOME pointed at a scratch dir), learns key weights on a
validation slice of the training weeks, then asks about every held-out
issue. Arms:

  A0   majority SIG
  S    the reporter's own /sig line, when there is one (not a model)
  A1   Ada, unweighted (glyph sim)            via the plugin
  A2   Ada, learned weights (exact weighted)   via the plugin
  A2p  A2's neighbours, temperature softmax -> calibrated probability
  A3   SVD latent space + temperature softmax -> calibrated probability

Usage: python run.py <data dir with issues.jsonl and fixes.json>
"""

import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ADA = HERE.parents[1]
sys.path.insert(0, str(ADA / "plugin"))
from glyphh_kernel import explain  # noqa: E402

from features import fix_dirs, situation, stated_sigs  # noqa: E402

CUTOFF = "2026-09-10"        # held out: issues opened on or after
VALID_FROM = "2026-08-13"    # last 4 training weeks: learn weights here
FIX_CUTOFF = "2026-08-06"    # fix retrieval: 8 held-out weeks (more fixes)
KEYS = ["kind", "components", "title", "paths"]
GRID = [0, 0.25, 0.5, 1, 2, 4]
MIN_SIM, K = 0.40, 7         # the plugin's own settings


# ── the plugin, over stdio ──────────────────────────────────────────

class Plugin:
    def __init__(self, home: Path):
        self.proc = subprocess.Popen(
            [sys.executable, str(ADA / "plugin" / "mcp" / "server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env={**os.environ, "GLYPHH_HOME": str(home)})
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-06-18"})

    def rpc(self, method, params):
        self.n += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": self.n, "method": method,
             "params": params}) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())["result"]

    def tool(self, name, **args):
        res = self.rpc("tools/call", {"name": name, "arguments": args})
        text = res["content"][0]["text"]
        if res["isError"]:
            raise RuntimeError(text)
        return json.loads(text)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


def build(plugin: Plugin, issues):
    """One win per (issue, SIG): the SIG that owned it is the outcome."""
    rid_to_issue = {}
    for r in issues:
        for sig in r["sigs"]:
            rid = plugin.tool("record", situation=r["sit"], outcome=sig,
                              author="k8s-train")["id"]
            rid_to_issue[rid] = r
    return rid_to_issue


# ── data ────────────────────────────────────────────────────────────

def load(data: Path):
    fixes = json.load(open(data / "fixes.json"))
    out = []
    for line in open(data / "issues.jsonl"):
        r = json.loads(line)
        r["sigs"] = sorted(l for l in r["labels"] if l.startswith("sig/"))
        r["sit"] = situation(r)
        r["fix"] = fix_dirs(fixes.get(str(r["number"]), []))
        r["prs"] = [p["number"] for p in fixes.get(str(r["number"]), [])]
        out.append(r)
    return sorted(out, key=lambda r: r["created_at"])


# ── learning weights on the validation slice (never the test) ───────

def key_scores(queries, rows):
    """S[q, i, k]: the fact tree's per-key score; U: key on either side."""
    S = np.zeros((len(queries), len(rows), len(KEYS)))
    U = np.zeros_like(S)
    for a, q in enumerate(queries):
        for b, r in enumerate(rows):
            for c in explain(q["sit"], r["sit"]).children:
                k = KEYS.index(c.key)
                S[a, b, k], U[a, b, k] = c.score, 1.0
    return S, U


def vote(scores, row_sigs, k=K, bar=MIN_SIM):
    """The plugin's read: top k, those clearing the bar vote by score."""
    order = np.argsort(scores, kind="stable")[::-1][:k]
    tally = defaultdict(float)
    for i in order:
        if scores[i] >= bar:
            for s in row_sigs[i]:
                tally[s] += scores[i]
    if not tally:
        return None, 0.0
    total = sum(tally.values())
    top = max(tally, key=tally.get)
    return top, tally[top] / total


def learn_weights(valid, base):
    S, U = key_scores(valid, base)
    sigs = [r["sigs"] for r in base]
    best = (-1, None)
    for w in itertools.product(GRID, repeat=len(KEYS)):
        w = np.array(w, dtype=float)
        if not w.any():
            continue
        den = (U * w).sum(-1)
        scores = np.where(den > 0, (S * U * w).sum(-1) / np.maximum(den, 1e-12), 0)
        hits = sum(vote(scores[a], sigs)[0] in q["sigs"]
                   for a, q in enumerate(valid))
        if hits > best[0]:
            best = (hits, w)
    return dict(zip(KEYS, best[1].tolist())), best[0] / len(valid)


# ── probability: temperature softmax over neighbours ────────────────

def softmax_probs(scores, row_sigs, tau, k=25):
    order = np.argsort(scores, kind="stable")[::-1][:k]
    tally = defaultdict(float)
    for i in order:
        for s in row_sigs[i]:
            tally[s] += math.exp(scores[i] / tau)
    z = sum(tally.values())
    return {s: v / z for s, v in tally.items()}


def fit_tau(score_rows, truths, row_sigs):
    """Temperature minimizing log-loss of the true SIG on validation."""
    best = (float("inf"), None)
    for tau in [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5]:
        loss = 0.0
        for scores, truth in zip(score_rows, truths):
            p = softmax_probs(scores, row_sigs, tau)
            loss -= math.log(max(sum(p.get(s, 0) for s in truth), 1e-6))
        if loss < best[0]:
            best = (loss, tau)
    return best[1]


# ── SVD: the store's latent case space ──────────────────────────────

def tokens(sit, w):
    out = {}
    for key, v in sit.items():
        for x in (v if isinstance(v, list) else [v]):
            out[f"{key}={x}"] = w.get(key, 1.0)
    return out


class Latent:
    def __init__(self, rows, w, rank):
        self.vocab = sorted({t for r in rows for t in tokens(r["sit"], w)})
        self.index = {t: i for i, t in enumerate(self.vocab)}
        A = np.stack([self.vec(r["sit"], w, raw=True) for r in rows])
        df = (A > 0).sum(0)
        self.idf = np.log((1 + len(rows)) / (1 + df)) + 1
        A = A * self.idf
        A /= np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-12)
        U, s, Vt = np.linalg.svd(A, full_matrices=False)
        self.V = Vt[:rank].T                     # vocab x rank
        self.rows = A @ self.V
        self.rows /= np.maximum(np.linalg.norm(self.rows, axis=1, keepdims=True), 1e-12)
        self.energy = float((s[:rank] ** 2).sum() / (s ** 2).sum())
        self.w = w

    def vec(self, sit, w, raw=False):
        v = np.zeros(len(self.vocab))
        for t, x in tokens(sit, w).items():
            if t in self.index:
                v[self.index[t]] = x
        return v if raw else v * self.idf

    def scores(self, sit):
        v = self.vec(sit, self.w)
        n = np.linalg.norm(v)
        if n == 0:
            return np.zeros(len(self.rows)), 1.0
        z = (v / n) @ self.V
        resid = 1 - float(np.linalg.norm(z) ** 2)  # novelty: off the subspace
        z /= max(np.linalg.norm(z), 1e-12)
        return self.rows @ z, resid


# ── grading ─────────────────────────────────────────────────────────

def ece(confs, hits, bins=10):
    confs, hits = np.array(confs), np.array(hits, dtype=float)
    total = 0.0
    for lo in np.linspace(0, 1, bins, endpoint=False):
        m = (confs >= lo) & (confs < lo + 1 / bins) if lo < 0.9 else confs >= lo
        if m.any():
            total += m.mean() * abs(confs[m].mean() - hits[m].mean())
    return total


def at_coverage(confs, hits, bar):
    m = [h for c, h in zip(confs, hits) if c >= bar]
    return (len(m) / len(hits), sum(m) / len(m) if m else float("nan"))


def report(name, preds, test):
    """preds: list of (ranked sig list, confidence) per test issue."""
    top1 = [bool(p[0]) and p[0][0] in r["sigs"] for p, r in zip(preds, test)]
    top3 = [bool(set(p[0][:3]) & set(r["sigs"])) for p, r in zip(preds, test)]
    confs = [p[1] for p in preds]
    out = {"arm": name, "top1": np.mean(top1), "top3": np.mean(top3),
           "ece": ece(confs, top1)}
    for bar in (0.5, 0.7, 0.9):
        cov, acc = at_coverage(confs, top1, bar)
        out[f"cov@{bar}"], out[f"acc@{bar}"] = cov, acc
    return out


def main(data: Path):
    issues = load(data)
    labeled = [r for r in issues if r["sigs"]]
    train = [r for r in labeled if r["created_at"] < CUTOFF]
    test = [r for r in labeled if r["created_at"] >= CUTOFF]
    base = [r for r in train if r["created_at"] < VALID_FROM]
    valid = [r for r in train if r["created_at"] >= VALID_FROM]
    print(f"train {len(train)} (base {len(base)} + valid {len(valid)}), "
          f"held out {len(test)} (opened {CUTOFF} or later)")

    weights, valid_acc = learn_weights(valid, base)
    print("learned weights:", weights, f"(validation top-1 {valid_acc:.2f})")

    # probability temperatures, fit on validation only
    base_sigs = [r["sigs"] for r in base]
    S, U = key_scores(valid, base)
    w = np.array([weights[k] for k in KEYS])
    den = (U * w).sum(-1)
    exact_valid = np.where(den > 0, (S * U * w).sum(-1) / np.maximum(den, 1e-12), 0)
    tau_exact = fit_tau(exact_valid, [r["sigs"] for r in valid], base_sigs)
    best_svd = None
    for rank in (16, 32, 64, 128):
        lat = Latent(base, weights, rank)
        rows = [lat.scores(r["sit"])[0] for r in valid]
        tau = fit_tau(rows, [r["sigs"] for r in valid], base_sigs)
        acc = np.mean([max(p := softmax_probs(s, base_sigs, tau), key=p.get) in r["sigs"]
                       for s, r in zip(rows, valid)])
        if best_svd is None or acc > best_svd[0]:
            best_svd = (acc, rank, tau)
    print(f"tau (exact) {tau_exact}; SVD rank {best_svd[1]}, tau {best_svd[2]} "
          f"(validation top-1 {best_svd[0]:.2f})")

    # the model: every training issue, through the plugin
    home = Path(tempfile.mkdtemp(prefix="ada-k8s-"))
    plugin = Plugin(home)
    rid_to_issue = build(plugin, train)
    print(f"plugin memory at {home}: {plugin.tool('status')}")

    train_sigs = [r["sigs"] for r in train]
    lat = Latent(train, weights, best_svd[1])
    counts = Counter(s for r in train for s in r["sigs"])
    majority = [s for s, _ in counts.most_common(3)]
    S, U = key_scores(test, train)
    den = (U * w).sum(-1)
    exact = np.where(den > 0, (S * U * w).sum(-1) / np.maximum(den, 1e-12), 0)
    arms = defaultdict(list)
    facts_of, novelty = [], []
    for n, r in enumerate(test):
        arms["A0 majority"].append((majority, counts[majority[0]] / sum(counts.values())))
        for name, kw in (("A1 ada", {}), ("A2 ada+weights", {"weights": weights})):
            a = plugin.tool("query", situation=r["sit"], **kw)
            ranked = sorted(a["outcomes"], key=a["outcomes"].get, reverse=True)
            arms[name].append((ranked, a["confidence"] if a["sufficient"] else 0.0))
        p = softmax_probs(exact[n], train_sigs, tau_exact)
        ranked = sorted(p, key=p.get, reverse=True)
        arms["A2p ada+weights+prob"].append((ranked, p[ranked[0]]))
        lsc, resid = lat.scores(r["sit"])
        p = softmax_probs(lsc, train_sigs, best_svd[2])
        ranked = sorted(p, key=p.get, reverse=True)
        arms["A3 svd+prob"].append((ranked, p[ranked[0]]))
        novelty.append(resid)
        facts_of.append(plugin.tool("facts", situation=r["sit"], weights=weights, top=3))
    plugin.close()

    rows = [report(name, preds, test) for name, preds in arms.items()]
    stated = [(r, stated_sigs(r)) for r in test]
    stated = [(r, ss) for r, ss in stated if ss]
    rows.append({"arm": "S reporter's /sig", "n": len(stated),
                 "top1": np.mean([ss[0] in r["sigs"] for r, ss in stated])})
    # where the reporter said nothing, the model is the only router
    silent = [i for i, r in enumerate(test) if not stated_sigs(r)]
    for name in ("A2 ada+weights", "A2p ada+weights+prob", "A3 svd+prob"):
        sub = [arms[name][i] for i in silent]
        row = report(name + " | no /sig", sub, [test[i] for i in silent])
        row["n"] = len(silent)
        rows.append(row)
    # novelty from the SVD residual: are novel cases the wrong ones?
    hits = [bool(p[0]) and p[0][0] in r["sigs"] for p, r in zip(arms["A3 svd+prob"], test)]
    med = float(np.median(novelty))
    nov = {"novel_acc": np.mean([h for h, x in zip(hits, novelty) if x > med]),
           "familiar_acc": np.mean([h for h, x in zip(hits, novelty) if x <= med])}
    result = {"weights": weights, "valid_top1": valid_acc, "tau_exact": tau_exact,
              "svd": {"rank": best_svd[1], "tau": best_svd[2], "energy": lat.energy},
              "arms": rows, "novelty": nov, "fix": fix_retrieval(issues, weights)}
    cards = [(r, f) for r, f in zip(test, facts_of)]
    return result, cards, rid_to_issue


def fix_retrieval(issues, weights):
    """Does the nearest SOLVED precedent point at the code that fixed a
    new issue? Model: issues with a linked fix opened before FIX_CUTOFF.
    Graded: issues opened after it whose fix is known."""
    solved = [r for r in issues if r["fix"] and r["created_at"] < FIX_CUTOFF]
    target = [r for r in issues if r["fix"] and r["created_at"] >= FIX_CUTOFF]
    home = Path(tempfile.mkdtemp(prefix="ada-k8s-fix-"))
    plugin = Plugin(home)
    rid = {}
    for r in solved:
        rid[plugin.tool("record", situation=r["sit"], outcome="fixed_by:" + ",".join(map(str, r["prs"])),
                        author="k8s-fixes")["id"]] = r
    common = [d for d, _ in Counter(d for r in solved for d in r["fix"]).most_common(3)]
    hit_ada, hit_common, hit_rand = [], [], []
    rng = np.random.default_rng(0)
    for r in target:
        f = plugin.tool("facts", situation=r["sit"], weights=weights, top=3)["wins"]
        near = set(d for x in f for d in rid[x["id"]]["fix"])
        hit_ada.append(bool(near & set(r["fix"])))
        hit_common.append(bool(set(common) & set(r["fix"])))
        rand = set(d for i in rng.choice(len(solved), 3, replace=False) for d in solved[i]["fix"])
        hit_rand.append(bool(rand & set(r["fix"])))
    plugin.close()
    return {"precedents": len(solved), "graded": len(target),
            "ada_top3_dir_hit": float(np.mean(hit_ada)),
            "top3_common_dirs_hit": float(np.mean(hit_common)),
            "random3_precedents_hit": float(np.mean(hit_rand))}


if __name__ == "__main__":
    result, cards, rid_to_issue = main(Path(sys.argv[1]))
    out = HERE / "results.json"
    out.write_text(json.dumps(result, indent=2, default=float))
    for row in result["arms"]:
        print("  ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()))
    print("novelty:", result["novelty"])
    print("fix retrieval:", result["fix"])
    with open(HERE / "cards.txt", "w") as fh:
        for r, f in cards:
            fh.write(f"#{r['number']} {r['title']}\n  truth: {r['sigs']}  situation: {json.dumps(r['sit'])}\n")
            for x in f["wins"]:
                src = rid_to_issue[x["id"]]
                fh.write(f"  -> {x['outcome']} score {x['score']} via #{src['number']} {src['title'][:70]}"
                         f"  fix PRs {src['prs']} dirs {src['fix'][:3]}\n")
                for c in x["tree"].get("children", []):
                    fh.write(f"       {c['key']}: score {c['score']} x w {c['weight']} -> {c['share']}\n")
            fh.write("\n")
