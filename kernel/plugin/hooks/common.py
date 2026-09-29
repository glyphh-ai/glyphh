"""Shared helpers for the glyphh hooks.

Hooks read the memory's SQLite files directly — no numpy, no kernel
import — so they run in milliseconds and cannot fail on dependencies.
The kernel is only needed by the agent itself, for real similarity
queries and writes.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

# per-session markers live in the system temp dir ($TMPDIR on macOS),
# not a hard-coded /tmp: sandboxed hosts may only allow writes there
MARKER_DIR = Path(tempfile.gettempdir()) / "glyphh-hooks"


def memory_dir() -> Path:
    """The one memory, the same in every session wherever it runs:
    $GLYPHH_HOME/ada, else ~/.glyphh/ada."""
    home = os.environ.get("GLYPHH_HOME") or str(Path.home() / ".glyphh")
    return Path(home) / "ada"


def rows(db_path: Path) -> List[Tuple[Dict[str, str], str, str]]:
    """(situation, outcome, author) for every precedent in a store."""
    if not db_path.exists():
        return []
    try:
        db = sqlite3.connect(str(db_path))
        cols = [r[1] for r in db.execute("PRAGMA table_info(precedents)")]
        select = ("SELECT situation, outcome, author FROM precedents"
                  if "author" in cols else
                  "SELECT situation, outcome, 'anon' FROM precedents")
        out = []
        for situation, outcome, author in db.execute(select):
            try:
                out.append((json.loads(situation), outcome, author))
            except (json.JSONDecodeError, TypeError):
                continue
        db.close()
        return out
    except sqlite3.Error:
        return []


def marker_path(session_id: str) -> Path:
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    return MARKER_DIR / f"{session_id}.json"


def read_marker(session_id: str) -> Dict:
    path = marker_path(session_id)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def write_marker(session_id: str, data: Dict) -> None:
    marker_path(session_id).write_text(json.dumps(data))
