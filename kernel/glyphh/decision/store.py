"""
Default persistent DecisionSpace for the runtime.

One process-wide space, SQLite-backed so recorded precedent survives
restarts. The HTTP routes and the MCP tools share this instance, so a
decision recorded through either surface is precedent for both.

Configuration:
    GLYPHH_DECISIONS_DB   path to the SQLite store
                          (default ~/.glyphh/decisions.db)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from .space import DecisionSpace

_space: Optional[DecisionSpace] = None
_lock = threading.Lock()


def default_persist_path() -> str:
    return os.environ.get(
        "GLYPHH_DECISIONS_DB",
        str(Path.home() / ".glyphh" / "decisions.db"),
    )


def get_default_space(dimension: int = 4096) -> DecisionSpace:
    global _space
    with _lock:
        if _space is None:
            _space = DecisionSpace(
                dimension=dimension,
                persist_path=default_persist_path(),
            )
        return _space


def reset_default_space() -> None:
    """Testing hook: drop the singleton so the next call reopens it."""
    global _space
    with _lock:
        _space = None
