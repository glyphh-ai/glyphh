"""The API key `glyphh login` keeps for this machine: ~/.glyphh/credentials.json, mode 0600 from its first byte,
written to a temporary name and renamed into place, so no reader ever sees half a file. `Ada()` reads it when no key
is given and GLYPHH_API_KEY is not set."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

#: What every Ada Cloud API key starts with.
KEY_PREFIX = "glyphh_ak_"


def credentials_path(home: Optional[Path] = None) -> Path:
    return (home or Path.home()) / ".glyphh" / "credentials.json"


def read_key(path: Optional[Path] = None) -> Optional[str]:
    """The kept API key; None when there is none."""
    try:
        v = json.loads((path or credentials_path()).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    key = v.get("api_key") if isinstance(v, dict) else None
    return key if isinstance(key, str) and key else None


def save_key(key: str, path: Optional[Path] = None) -> Path:
    path = path or credentials_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"api_key": key}, indent=2) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def forget_key(path: Optional[Path] = None) -> bool:
    """Forgets the kept key here; False when there was none. The key itself stays live until revoked."""
    try:
        (path or credentials_path()).unlink()
    except FileNotFoundError:
        return False
    return True
