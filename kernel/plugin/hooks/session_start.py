"""SessionStart: inject the memory's state into context at boot.

Recall is not left to the agent's discretion — the session starts
already knowing what its memory holds. Silent in workspaces that
don't use glyphh.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import has_kernel, memory_dir, rows, write_marker


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    cwd = data.get("cwd", ".")
    mem = memory_dir(cwd)
    if mem is None:
        if has_kernel(cwd):
            print("This workspace contains glyphh_kernel.py but no memory "
                  "store yet. The glyphh-memory skill covers creating one "
                  "when graded, recurring decisions appear.")
        return

    wins = rows(mem / "wins.db")
    vetoes = rows(mem / "vetoes.db")
    write_marker(data.get("session_id", "unknown"), {
        "start": time.time(),
        "memory_dir": str(mem),
        "wins": len(wins),
        "vetoes": len(vetoes),
        "nagged": False,
    })

    lines = [f"glyphh memory at {mem} — {len(wins)} wins, "
             f"{len(vetoes)} vetoes."]
    kinds = Counter()
    for situation, _, _ in wins:
        for key in ("task", "kind", "topic"):
            if key in situation:
                kinds[situation[key]] += 1
                break
    if kinds:
        top = ", ".join(f"{k} ({n})" for k, n in kinds.most_common(6))
        lines.append(f"Known situation kinds: {top}.")
    if vetoes:
        vetoed = sorted({outcome for _, outcome, _ in vetoes})[:6]
        lines.append(f"Vetoed approaches: {', '.join(vetoed)}.")
    authors = sorted({a for _, _, a in wins + vetoes})
    if len(authors) > 1:
        lines.append(f"Contributors: {', '.join(authors)}.")
    lines.append("Query this memory before repeating a kind of decision; "
                 "record graded outcomes as they land (glyphh-memory "
                 "skill has the loop).")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
