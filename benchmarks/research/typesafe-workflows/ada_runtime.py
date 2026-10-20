"""Ada on Security Incidents through the product: the one Ada model (ada_model/) deployed on an rrotor runtime and
driven with the published SDK (`pip install glyphh`), in Jev's place in TypeSafe's workflow on the frozen test set.

The model is recorded with every development case once (each with the consensus's answer to every question it was
asked), refreshed (each question learns and calibrates), and then answers each test case's questions as the
workflow asks them (decide_all); security.decide(), the same policy code Jev is scored by, turns the answers into
the action. Nothing here needs the kernel: the runtime's Ada part brings it.

    uv run python ada_runtime.py spec          # write ada_model/spec.json from ada.py (commit it, then publish)
    git subtree split --prefix typesafe-workflows/ada_model -b ada-model && git push origin ada-model
    BENCH_SET=test uv run python ada_runtime.py

The runtime: GLYPHH_RUNTIME_URL and GLYPHH_RUNTIME_KEY, or ~/.config/glyphh/runtime (its URL on the first line,
a runtime key on the second). GLYPHH_RUNTIME_HOST, when set, is sent as the Host header (a local runtime that
answers only its public host). The model is deployed from MODEL_REPO's MODEL_BRANCH at the commit the local branch
names, after checking its spec.json is ada.py's.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import glyphh

import ada
import run
import score
import security

HERE = Path(__file__).parent
MODEL_DIR = HERE / "ada_model"
MODEL_REPO = "glyphh-ai/benchmarks"
MODEL_BRANCH = "ada-model"
MODEL = "security-incidents"


def write_spec() -> None:
    """ada_model/spec.json: ada.py's spec, every workflow question an output."""
    (MODEL_DIR / "spec.json").write_text(json.dumps(ada.spec(), indent=2) + "\n")
    print(f"wrote {MODEL_DIR / 'spec.json'}")


def runtime() -> glyphh.Ada:
    url, key = os.environ.get("GLYPHH_RUNTIME_URL"), os.environ.get("GLYPHH_RUNTIME_KEY")
    if not (url and key):
        lines = (Path.home() / ".config/glyphh/runtime").read_text().split()
        url, key = lines[0], lines[1]
    host = os.environ.get("GLYPHH_RUNTIME_HOST")
    if not host:
        return glyphh.Ada(url, key)

    def transport(method, target, headers, body):
        return glyphh.client._urllib(method, target, {**headers, "Host": host}, body)

    return glyphh.Ada(url, key, transport=transport)


def published_commit() -> str:
    """The model's commit: the local MODEL_BRANCH, pushed, its spec.json ada.py's own."""
    sha = subprocess.run(["git", "rev-parse", MODEL_BRANCH], capture_output=True, text=True, check=True).stdout.strip()
    remote = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{MODEL_REPO}", MODEL_BRANCH], capture_output=True, text=True, check=True
    ).stdout.split()
    if not remote or remote[0] != sha:
        sys.exit(f"{MODEL_BRANCH} ({sha[:12]}) is not what {MODEL_REPO} holds; push it first")
    shipped = json.loads(subprocess.run(["git", "show", f"{sha}:spec.json"], capture_output=True, text=True, check=True).stdout)
    if shipped != ada.spec():
        sys.exit(f"{MODEL_BRANCH}'s spec.json is not ada.py's spec: write it again (spec), commit, split and push")
    return sha


def done(result: glyphh.Result) -> dict:
    if not result.done:
        sys.exit(f"{MODEL}: {result.status} {result.data}")
    return result.data


def main() -> None:
    if run.SET != "test":
        sys.exit("the runtime run is the frozen test set's: BENCH_SET=test")
    labels = score.consensus_actions()
    dev = run.cases("dev")
    reference = {c["id"]: run.consensus(c["id"], "dev") for c in dev}
    train = [c for c in dev if all(q in reference[c["id"]] for q in ("is_true_positive", "context_explains_activity"))]
    tests = [c for c in run.cases() if c["id"] in labels]

    client = runtime()
    commit = published_commit()
    deployed = client.deploy(MODEL_REPO, commit)
    print(f"deployed {deployed['model']} v{deployed['version']} ({commit[:12]})", file=sys.stderr)
    model = client.model(MODEL)

    t0 = time.time()
    counts: dict[str, dict[str, int]] = {}
    for c in train:
        answers = ada.graded(c, reference)
        done(model.call("record", {"data": ada.situation(c), "outcomes": answers}))
        for q, outcome in answers.items():
            counts.setdefault(q, {})[outcome] = counts.setdefault(q, {}).get(outcome, 0) + 1
    print(f"recorded {len(train)} cases in {time.time() - t0:.0f}s", file=sys.stderr)
    done(model.call("refresh"))
    questions = ada.spec()["outputs"]
    base = {q: {o: counts.get(q, {}).get(o, 0) for o in questions[q]["values"]} for q in questions}

    import published

    asked = published.questions("security_incidents")

    def answer(qs, data):
        decided = done(model.call("decide_all", {"data": data, "outputs": list(qs)}))
        out = {}
        for q in qs:
            outcome = decided[q]["outcome"] or max(base[q], key=base[q].get)
            if asked[q]["type"] == "noul":
                out[q] = ada.zones(q)[outcome]
            else:
                out[q] = {o: 1.0 if o == outcome else 0.0 for o in ada.options(q, asked[q])}
        return out

    out = {}
    for c in tests:
        t1 = time.time()
        data = ada.situation(c)
        action, answers = security.decide(lambda qs, data=data: answer(qs, data), c)
        out[c["id"]] = {"action": action, "answers": answers, "seconds": time.time() - t1, "dollars": 0.0}
    run.save("ada", out)
    right = sum(out[c]["action"] == labels[c] for c in out)
    print(f"ada ({run.SET}, rrotor): {right} of {len(out)} match the consensus (trained on {len(train)} development cases)")


if __name__ == "__main__":
    write_spec() if sys.argv[1:] == ["spec"] else main()
