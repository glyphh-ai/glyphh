"""TypeSafe's published workflow evals (evals.typesafe.ai): the questions each workflow asks and the example cases.

Nothing of theirs is kept in this repository; `fetch()` downloads the viewer data into data/published/ (git-ignored)
and everything else reads it from there.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
PUBLISHED = HERE / "data" / "published"
SITE = "https://evals.typesafe.ai"
WORKFLOWS = (
    "security_incidents",
    "agent_trace_observability",
    "invoice_processing",
    "customer_service",
)


def fetch() -> None:
    PUBLISHED.mkdir(parents=True, exist_ok=True)
    for w in WORKFLOWS:
        request = urllib.request.Request(
            f"{SITE}/{w}-cases.js", headers={"User-Agent": "curl/8"}
        )
        with urllib.request.urlopen(request, timeout=60) as r:  # noqa: S310  (a fixed https URL)
            (PUBLISHED / f"{w}-cases.js").write_bytes(r.read())
        print(f"{w}: {(PUBLISHED / f'{w}-cases.js').stat().st_size:,} bytes")


def load(workflow: str) -> dict:
    """The eval's viewer data: n_cases, questions, example documents and every model's answers on them."""
    path = PUBLISHED / f"{workflow}-cases.js"
    if not path.exists():
        fetch()
    s = path.read_text()
    return json.loads(s[s.index("(") + 1 : s.rindex(")")])["eval"]


def questions(workflow: str) -> dict[str, dict]:
    """{question id: question} for every question the workflow can ask, ids as TypeSafe's nodes name them."""
    e = load(workflow)
    ids: dict[int, str] = {}
    for case in e["cases"].values():
        for node in case["models"]["typesafe"]["nodes"]:
            for qid, index in node["questions"].items():
                ids[index] = qid
    return {ids[i]: q for i, q in enumerate(e["questions"]) if i in ids}


def nodes(workflow: str) -> dict[str, list[str]]:
    """{node: [question ids]} in the order TypeSafe's workflow asks them."""
    out: dict[str, list[str]] = {}
    for case in load(workflow)["cases"].values():
        for node in case["models"]["typesafe"]["nodes"]:
            if node["questions"]:
                out[node["node"]] = sorted(node["questions"], key=node["questions"].get)
    return out


if __name__ == "__main__":
    fetch()
