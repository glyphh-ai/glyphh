"""
Session memory for the agent working on this repo, built on the kernel.

The agent (Claude, in the session that wrote this) records graded
operational experience — what worked and what failed while working on
this codebase — and queries it before repeating a kind of decision.
Usage is journaled in LOG.md; the stores are wins.db / vetoes.db next
to this file (committed: they ARE the experience).

  python3 kernel/dogfood/mem.py record '{"task": "push"}' outcome_name
  python3 kernel/dogfood/mem.py record '{"task": "push"}' bad_idea --fail
  python3 kernel/dogfood/mem.py query  '{"task": "push"}'
  python3 kernel/dogfood/mem.py veto   '{"task": "push"}' outcome_name
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glyphh_kernel import Space  # noqa: E402

HERE = Path(__file__).parent
# Session situations are small (2-3 attrs), so "same kind of situation"
# means most attributes shared: min_sim 0.4 per KERNEL.md sizing rule.
AUTHOR = "claude-main"
WINS = dict(min_sim=0.40, k=7, author=AUTHOR, path=str(HERE / "wins.db"))
VETOES = dict(min_sim=0.40, k=7, author=AUTHOR, path=str(HERE / "vetoes.db"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=["record", "query", "veto"])
    parser.add_argument("situation", help="JSON dict of attributes")
    parser.add_argument("outcome", nargs="?", default=None)
    parser.add_argument("--fail", action="store_true",
                        help="record into the veto space")
    args = parser.parse_args()
    situation = json.loads(args.situation)

    if args.verb == "record":
        if not args.outcome:
            sys.exit("record needs an outcome")
        with Space(**(VETOES if args.fail else WINS)) as space:
            rid = space.record(situation, args.outcome)
        print(json.dumps({"recorded": rid, "space":
                          "vetoes" if args.fail else "wins"}))
    elif args.verb == "query":
        with Space(**WINS) as wins:
            answer = wins.query(situation)
        out = answer.to_json()
        if answer.top:
            with Space(**VETOES) as vetoes:
                out["veto_sim"] = round(
                    vetoes.matches(situation, answer.top), 4)
        print(json.dumps(out))
    else:  # veto check for a specific contemplated action
        if not args.outcome:
            sys.exit("veto needs an outcome to check")
        with Space(**VETOES) as vetoes:
            print(json.dumps(
                {"veto_sim": round(vetoes.matches(situation, args.outcome), 4)}))


if __name__ == "__main__":
    main()
