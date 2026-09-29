"""UserPromptSubmit: inject precedent relevant to the incoming prompt.

The hook does exact-overlap matching against stored situations (fast,
sqlite-only) and injects hits with their outcomes and veto status —
recall happens TO the agent, per prompt, like the entity's step()
queries before acting. The agent runs real similarity queries itself
when it needs more than this surfaces.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import memory_dir, rows

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "at",
    "is", "are", "it", "this", "that", "with", "as", "be", "do", "can",
    "you", "your", "we", "our", "i", "me", "my", "please", "then",
    "now", "just", "also", "how", "what", "when", "why", "not", "no",
}


def tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9_]{3,}", text.lower())
            if t not in STOP_WORDS}


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    mem = memory_dir(data.get("cwd", "."))
    if mem is None:
        return
    prompt_tokens = tokens(data.get("prompt", ""))
    if not prompt_tokens:
        return

    wins = rows(mem / "wins.db")
    vetoes = rows(mem / "vetoes.db")

    # Group identical situations; score by token overlap with the prompt.
    def situation_tokens(situation: dict) -> set:
        out = set()
        for key, value in situation.items():
            out |= tokens(str(key)) | tokens(str(value).replace("_", " "))
        return out

    scored = []
    grouped = defaultdict(lambda: {"wins": defaultdict(int), "vetoes": set()})
    for situation, outcome, _ in wins:
        grouped[json.dumps(situation, sort_keys=True)]["wins"][outcome] += 1
    for situation, outcome, _ in vetoes:
        grouped[json.dumps(situation, sort_keys=True)]["vetoes"].add(outcome)

    for key, entry in grouped.items():
        situation = json.loads(key)
        overlap = situation_tokens(situation) & prompt_tokens
        if len(overlap) >= 2:
            scored.append((len(overlap), situation, entry))
    if not scored:
        return

    scored.sort(key=lambda x: -x[0])
    lines = ["glyphh memory hits for this prompt (exact-overlap; run a "
             "similarity query for anything borderline):"]
    for _, situation, entry in scored[:3]:
        parts = []
        if entry["wins"]:
            worked = ", ".join(f"{o} (x{n})" for o, n in
                               sorted(entry["wins"].items(), key=lambda x: -x[1]))
            parts.append(f"worked: {worked}")
        if entry["vetoes"]:
            parts.append(f"vetoed: {', '.join(sorted(entry['vetoes']))}")
        lines.append(f"- {json.dumps(situation, sort_keys=True)} -> "
                     + "; ".join(parts))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
