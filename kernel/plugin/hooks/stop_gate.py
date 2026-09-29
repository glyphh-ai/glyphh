"""Stop: the LEARN gate. Once per session, if the memory exists and
nothing was recorded, block the stop and ask the agent to record
graded outcomes or state that nothing was graded. Mirrors the
entity's loop, where LEARN is not optional — but nags exactly once,
because a session may legitimately grade nothing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import read_marker, write_marker


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if data.get("stop_hook_active"):
        sys.exit(0)  # never loop on our own block

    session_id = data.get("session_id", "unknown")
    marker = read_marker(session_id)
    if not marker or marker.get("nagged"):
        sys.exit(0)  # no glyphh workspace this session, or already asked

    mem = Path(marker.get("memory_dir", ""))
    if not mem.exists():
        sys.exit(0)

    def count(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            import sqlite3
            db = sqlite3.connect(str(path))
            n = db.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]
            db.close()
            return n
        except Exception:
            return 0

    recorded = (count(mem / "wins.db") - marker.get("wins", 0)
                + count(mem / "vetoes.db") - marker.get("vetoes", 0))
    if recorded > 0:
        sys.exit(0)  # the loop closed itself this session

    marker["nagged"] = True
    write_marker(session_id, marker)
    print("glyphh memory: nothing has been recorded this session. If any "
          "decision was graded by its outcome (a command worked or "
          "failed, a fix held, the user accepted or corrected an "
          "approach), record it to wins/vetoes now per the glyphh-think "
          "skill. If nothing was graded, say so and finish — this "
          "reminder fires once per session.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
