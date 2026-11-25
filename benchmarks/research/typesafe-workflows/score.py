"""Score the Security Incidents run the way TypeSafe does: each contestant's action against the consensus action
(the policy run on the mean of the references' probabilities), with cost and time per case.

    uv run python score.py
"""

from __future__ import annotations

import run
import security


def consensus_actions() -> dict[str, str]:
    """The reference: the policy on the mean of both references' probabilities, for every case both answered."""
    out = {}
    for case in run.cases():
        both = run.consensus(case["id"])
        try:
            out[case["id"]], _ = security.decide(
                lambda qs, both=both: {q: both[q] for q in qs}, case
            )
        except KeyError:
            continue  # a reference has not answered this case yet
    return out


def reference_actions(name: str, ids) -> dict[str, str]:
    cases = {c["id"]: c for c in run.cases()}
    answers = run.load(name)
    out = {}
    for cid in ids:
        a = answers.get(cid, {}).get("answers", {})
        try:
            out[cid], _ = security.decide(
                lambda qs, a=a: {q: a[q] for q in qs}, cases[cid]
            )
        except KeyError:
            pass
    return out


def main() -> None:
    reference = consensus_actions()
    print(f"consensus reference on {len(reference)} of {len(run.cases())} cases")
    if not reference:
        return
    rows = [
        (f"{name} (a reference)", reference_actions(name, reference), None)
        for name in run.REFERENCES
    ]
    for name, label in (("jev", "Jev"), ("ada", "Ada")):
        got = run.load(name)
        rows.append(
            (label, {cid: got[cid]["action"] for cid in reference if cid in got}, got)
        )

    print(
        f"{'':22s} {'accuracy':>9s} {'cases':>6s} {'$ per case':>11s} {'s per case':>11s}"
    )
    for name, decided, raw in rows:
        if not decided:
            continue
        right = sum(decided[c] == reference[c] for c in decided)
        cost = time = ""
        if raw:
            cost = f"{sum(raw[c]['dollars'] for c in decided) / len(decided):11.5f}"
            time = f"{sum(raw[c]['seconds'] for c in decided) / len(decided):11.3f}"
        print(
            f"{name:22s} {right / len(decided):9.1%} {len(decided):6d} {cost:>11s} {time:>11s}"
        )
    counts: dict[str, int] = {}
    for action in reference.values():
        counts[action] = counts.get(action, 0) + 1
    print("\nconsensus actions:", dict(sorted(counts.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
