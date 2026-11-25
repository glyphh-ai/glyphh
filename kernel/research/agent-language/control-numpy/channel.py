"""The shared channel. Every agent posts and reads through this file.

    from channel import post, read
    post("courier", "all", "text for humans", payload=some_array, kind="note")
    for m in read(since=0): ...        # every message, oldest first

A message is one JSON line in channel/log.jsonl. `payload` (optional) is
a numpy array of any shape and dtype, stored base64 with its dtype and
shape, so another agent can decode it instead of reading `text`.
"""

import base64
import fcntl
import json
import time
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

LOG = Path(__file__).resolve().parent / "channel" / "log.jsonl"


def post(sender: str, to: str, text: str, payload: Optional[np.ndarray] = None,
         kind: str = "note", **extra) -> dict:
    msg = {"ts": time.time(), "from": sender, "to": to, "kind": kind,
           "text": text, **extra}
    if payload is not None:
        a = np.ascontiguousarray(payload)
        msg["payload"] = {"b64": base64.b64encode(a.tobytes()).decode(),
                          "dtype": str(a.dtype), "shape": list(a.shape)}
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
        if "payload" in msg:
            p = msg["payload"]
            msg["payload"] = np.frombuffer(
                base64.b64decode(p["b64"]), dtype=p["dtype"]).reshape(p["shape"]).copy()
        yield msg
