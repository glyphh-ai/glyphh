"""Shared helpers for the glyphh hooks.

Hooks read the memory's SQLite files directly — no numpy, no kernel
import — so they run in milliseconds and cannot fail on dependencies.
The kernel is only needed by the agent itself, for real similarity
queries and writes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MARKER_DIR = Path("/tmp/glyphh-hooks")


def memory_dir(cwd: str) -> Optional[Path]:
    """The workspace's memory directory, or None if this workspace
    doesn't use glyphh (the plugin then stays silent)."""
    root = Path(cwd)
    for name in ("dogfood", ".glyphh", "memory"):
        candidate = root / name
        if (candidate / "wins.db").exists() or (candidate / "vetoes.db").exists():
            return candidate
    return None


def has_kernel(cwd: str) -> bool:
    return (Path(cwd) / "glyphh_kernel.py").exists()


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
