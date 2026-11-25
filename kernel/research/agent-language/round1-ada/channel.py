"""The shared channel. Every agent posts and reads through this file.

    from channel import post, read
    post("courier", "all", "text for humans", glyph=some_glyph, kind="note")
    for m in read(since=0): ...        # every message, oldest first

A message is one JSON line in channel/log.jsonl. `glyph` (optional) is a
kernel glyph (numpy int8 vector, dim 4096), stored base64 so another
agent can decode it with the shared language instead of reading `text`.
"""

import base64
import fcntl
import json
import time
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

LOG = Path(__file__).resolve().parent / "channel" / "log.jsonl"


def post(sender: str, to: str, text: str, glyph: Optional[np.ndarray] = None,
         kind: str = "note", **extra) -> dict:
    msg = {"ts": time.time(), "from": sender, "to": to, "kind": kind,
           "text": text, **extra}
    if glyph is not None:
        msg["glyph"] = base64.b64encode(
            np.asarray(glyph, dtype=np.int8).tobytes()).decode()
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(msg) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    return msg


def read(since: float = 0.0, to: Optional[str] = None) -> Iterator[dict]:
    if not LOG.exists():
        return
    for line in LOG.read_text().splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg["ts"] <= since:
            continue
        if to and msg["to"] not in (to, "all"):
            continue
        if "glyph" in msg:
            msg["glyph"] = np.frombuffer(
                base64.b64decode(msg["glyph"]), dtype=np.int8).copy()
        yield msg
