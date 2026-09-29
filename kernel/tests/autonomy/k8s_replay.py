"""
The autonomy claim against public, unsanitized reality:
Kubernetes issue triage, replayed from GH Archive.

Task     a new kubernetes/kubernetes issue arrives; route it to a SIG
         (26 possible sig/* labels). The world's grade: the SIG labels
         the issue actually carried when it was CLOSED — assigned by
         the k8s triage process, not by us. Multi-label: routing to
         any SIG the issue ended up with counts as correct.

Data     every sig-labeled IssuesEvent(action=closed) on
         kubernetes/kubernetes in the ClickHouse GH Archive mirror
         (play.clickhouse.com, coverage 2023-2026), replayed in close
         order. 2,591 unique issues. Nothing curated, nothing synthetic.

Run      python3 tests/autonomy/k8s_replay.py --mode dry            (free)
         python3 tests/autonomy/k8s_replay.py --mode llm-sample     (~$2)
         python3 tests/autonomy/k8s_replay.py --mode live           (~$5-15)

Not named test_* on purpose: the live modes spend real API money and
must be invoked deliberately, never by pytest collection.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.autonomy.entity import AutonomousEntity  # noqa: E402

DATA = Path(os.environ.get(
    "K8S_ISSUES_JSONL",
    Path(__file__).parent / "data" / "k8s_closed_sig_issues.jsonl"))

STOP = set("""a an the and or of to in for is are was were be been on at by
with from as it this that these those not no can will would should could has
have had do does did if then than so such via when what which who how where
why you your we our they their i me my him her its about into over under out
up down off after before again more most other some any only same too very
just also there here kubernetes k8s kube issue bug version happened expected
reproduce environment steps possible anything else need know https github.com
com www http""".split())


def load_issues() -> List[dict]:
    rows = [json.loads(line) for line in DATA.open()]
    dedup: Dict[int, dict] = {}
    for row in rows:  # keep the FIRST close of reopened issues
        dedup.setdefault(row["number"], row)
    return sorted(dedup.values(), key=lambda r: r["closed_at"])


def title_tokens(title: str, cap: int = 40) -> List[str]:
    """The situation encoding: distinct informative title tokens."""
    text = re.sub(r"```.*?```", " ", title.lower(), flags=re.S)
    out, seen = [], set()
    for tok in re.findall(r"[a-z][a-z0-9_.-]{2,}", text):
        if tok in STOP or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= cap:
            break
    return out


def situation_of(issue: dict) -> Dict[str, str]:
    toks = title_tokens(issue["title"])
    return {t: t for t in toks} or {"empty": "empty"}


# ── proposers ───────────────────────────────────────────────────────

class NoisyOracle:
    """Dry-run stand-in for the LLM: right at a set rate, never grounded."""

    def __init__(self, accuracy: float, actions: List[str], seed: int = 11):
        self.accuracy = accuracy
        self.actions = actions
        self.calls = 0
        self.cost_usd = 0.0
        self._rng = random.Random(seed)
        self._truth: Set[str] = set()

    def set_truth(self, sigs: Set[str]) -> None:
        self._truth = sigs

    def __call__(self, situation, events, actions) -> str:
        self.calls += 1
        if self._rng.random() < self.accuracy and self._truth:
            return self._rng.choice(sorted(self._truth))
        return self._rng.choice(actions)


class K8sSigProposer:
    """A real Claude routing one issue to one SIG. Same contract."""

    SYSTEM = (
        "You are a Kubernetes issue triager. Given a new issue on "
        "kubernetes/kubernetes, assign it to the single most appropriate "
        "SIG. Reply with EXACTLY one label from the provided list — "
        "nothing else."
    )

    def __init__(self, actions: List[str], model: str = "claude-opus-5-5"):
        import anthropic
        self._client = anthropic.Anthropic()
        self._model = model
        self._actions = actions
        self._rng = random.Random(3)
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._issue: Optional[dict] = None

    def set_issue(self, issue: dict) -> None:
        self._issue = issue

    def __call__(self, situation, events, actions) -> str:
        import anthropic
        self.calls += 1
        issue = self._issue or {}
        body = (issue.get("body") or "")[:1200]
        prompt = (
            f"Issue title: {issue.get('title', '')}\n"
            f"Issue body (truncated):\n{body}\n\n"
            f"SIG labels: {', '.join(actions)}\n"
            f"Label:"
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=self.SYSTEM,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
            )
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
            if response.stop_reason == "refusal":
                return self._rng.choice(actions)
            text = next((b.text for b in response.content
                         if b.type == "text"), "").strip().lower()
            for action in actions:
                if action in text:
                    return action
        except anthropic.APIError:
            pass
        return self._rng.choice(actions)

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * 4 + self.output_tokens * 20) / 1e6


# ── baselines ───────────────────────────────────────────────────────

def majority_prequential(issues: List[dict]) -> float:
    counts: Counter = Counter()
    n = hits = 0
    for issue in issues:
        truth = set(issue["sigs"])
        if counts:
            n += 1
            hits += counts.most_common(1)[0][0] in truth
        for sig in issue["sigs"]:
            counts[sig] += 1
    return hits / n


def tfidf_prequential(issues: List[dict], retrain_every: int = 250,
                      warmup: int = 50) -> float:
    """TF-IDF + LogisticRegression, retrained as closes arrive.
    The strongest classical online baseline for this task."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    texts = [i["title"] + " " + (i["body"] or "") for i in issues]
    labels = [i["sigs"][0] for i in issues]
    model = vec = None
    n = hits = 0
    for i in range(len(issues)):
        if i >= warmup and (model is None or i % retrain_every == 0):
            vec = TfidfVectorizer(max_features=20000, sublinear_tf=True,
                                  ngram_range=(1, 2))
            model = LogisticRegression(max_iter=1000, C=4.0).fit(
                vec.fit_transform(texts[:i]), labels[:i])
        if model is not None:
            pred = model.predict(vec.transform([texts[i]]))[0]
            n += 1
            hits += pred in set(issues[i]["sigs"])
    return hits / n


# ── the replay ──────────────────────────────────────────────────────

def replay(issues: List[dict], proposer, actions: List[str],
           limit: Optional[int] = None) -> AutonomousEntity:
    entity = AutonomousEntity(
        proposer=proposer, actions=actions,
        dimension=4096, act_threshold=0.5, k=15, min_sim=0.10)
    for issue in issues[:limit]:
        truth = set(issue["sigs"])
        if hasattr(proposer, "set_truth"):
            proposer.set_truth(truth)
        if hasattr(proposer, "set_issue"):
            proposer.set_issue(issue)
        entity.step(situation_of(issue), events=[],
                    grade=lambda action, t=truth: action in t)
    return entity


def report(entity: AutonomousEntity, proposer, issues: List[dict]) -> dict:
    quartiles = entity.quartile_stats()
    consults = [r for r in entity.history if r.mode == "consult"]
    reflexes = [r for r in entity.history if r.mode == "reflex"]
    out = {
        "issues_replayed": len(entity.history),
        "quartiles": quartiles,
        "overall_accuracy": sum(r.success for r in entity.history)
        / len(entity.history),
        "reflex_share": len(reflexes) / len(entity.history),
        "reflex_accuracy": (sum(r.success for r in reflexes)
                            / len(reflexes)) if reflexes else None,
        "consult_accuracy": (sum(r.success for r in consults)
                             / len(consults)) if consults else None,
        "llm_calls": proposer.calls,
        "llm_cost_usd": round(getattr(proposer, "cost_usd", 0.0), 3),
        "precedents": entity.precedents,
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dry", "llm-sample", "live"],
                        default="dry")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--sim-accuracy", type=float, default=0.55)
    args = parser.parse_args()

    issues = load_issues()
    actions = sorted({s for i in issues for s in i["sigs"]})
    print(f"{len(issues)} issues, {len(actions)} SIGs")

    if args.mode == "llm-sample":
        rng = random.Random(0)
        sample = rng.sample(issues, args.sample)
        proposer = K8sSigProposer(actions)
        hits = 0
        for i, issue in enumerate(sample):
            proposer.set_issue(issue)
            pred = proposer({}, [], actions)
            hits += pred in set(issue["sigs"])
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(sample)} acc so far "
                      f"{hits/(i+1):.3f} ~${proposer.cost_usd:.2f}")
        print(json.dumps({
            "llm_alone_accuracy": hits / len(sample),
            "n": len(sample),
            "cost_usd": round(proposer.cost_usd, 3),
        }, indent=2))
        return

    print(f"majority prequential: {majority_prequential(issues):.3f}")
    print(f"tfidf+LR prequential: {tfidf_prequential(issues):.3f}")

    if args.mode == "dry":
        proposer = NoisyOracle(args.sim_accuracy, actions)
    else:
        proposer = K8sSigProposer(actions)

    entity = replay(issues, proposer, actions, limit=args.limit)
    print(json.dumps(report(entity, proposer, issues), indent=2))


if __name__ == "__main__":
    main()
