"""The Resume Screener's timing check: what the timestamps on an email say of how it travelled. The `Date` header
is the time the sender's program says it was written; each `Received` header is the time a mail server says it took
the message in, the first server at the bottom and the last at the top. `read` measures them: how long after its
date the first server had it, whether the servers' times run in order, the longest wait between two servers, a date
that lies after a server already had the message (or after now), and the hour on the sender's own clock. `windows`
names the ten minutes it arrived in, twice over, so that Ada can be asked which other applications arrived close to
it (others.py); `with_burst` adds how many did. `flags` names what a person would want to know and `found` says
each in a sentence. It measures and names; whether a flag matters is the person's to teach."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

SKEW: int = 120  # seconds two honest clocks may disagree by
LONG: int = 3600  # seconds: a wait this long between two points is named
ODD: range = range(1, 5)  # the hours on the sender's own clock named as odd: 01:00 to 04:59
WINDOW: int = 600  # seconds: applications that arrive in one window arrived together
BURST: int = 3  # this many other applications in the window make a burst
GAP_MIN, GAP_MAX, WAIT_MAX = -600, 3600, 7200  # what the model's numbers are kept within
SAID: dict[str, str] = {
    "no_date": "the email has no date that can be read",
    "no_hops": "the email carries no server timestamps, so how it travelled is not known",
    "future_date": "the email is dated after a server already had it, or after now",
    "held_back": "the email is dated more than an hour before the first server had it",
    "out_of_order": "the servers' timestamps do not run in order",
    "long_gap": "the email waited more than an hour between two servers",
    "odd_hour": "it was sent between 1 and 5 in the morning on the sender's own clock",
    "burst": "{n} other applications arrived within ten minutes of it",
}


def stamp(said: str) -> datetime | None:
    """A header's time; one that names no zone is read as UTC. None: it is not a time."""
    try:
        got = parsedate_to_datetime(said.strip())
    except (TypeError, ValueError, IndexError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def hops(received: list[str]) -> list[datetime]:
    """The servers' times, the first server first (the headers are given the last server first). A Received header
    gives its time after its last semicolon; one with no time that can be read is left out."""
    times = [stamp(line.rsplit(";", 1)[1]) for line in received if ";" in line]
    return [t for t in reversed(times) if t is not None]


def _within(n: float, low: int, high: int) -> int:
    return int(max(low, min(high, n)))


def windows(at: datetime) -> list[str]:
    """The ten minutes `at` falls in, named twice: once on the clock's own tens and once five minutes off them, so
    two messages within five minutes of each other always share a name."""
    seconds = int(at.timestamp())
    return [f"a{seconds // WINDOW}", f"b{(seconds + WINDOW // 2) // WINDOW}"]


def read(date: str, received: list[str], now: datetime | None = None) -> dict[str, Any]:
    """The email's timing as the timing model reads it. A number that cannot be known is left out."""
    sent, took = stamp(date) if date else None, hops(received)
    gaps = [(b - a).total_seconds() for a, b in zip(took, took[1:], strict=False)]
    first = (took[0] - sent).total_seconds() if sent and took else None
    arrived = took[-1] if took else sent
    late = now is not None and sent is not None and (sent - now).total_seconds() > SKEW
    out: dict[str, Any] = {
        "dated": "yes" if sent else "no",
        "hops": min(len(took), 20),
        "order": "none" if len(took) < 2 else "out_of_order" if min(gaps) < -SKEW else "in_order",
        "zone": sent.strftime("%z") if sent else "none",
        "arrived": arrived.astimezone(UTC).isoformat(timespec="seconds") if arrived else "",
        "windows": windows(arrived) if arrived else [],
        "burst": 0,
    }
    if sent:
        out["local_hour"] = sent.hour
    if first is not None:
        out["first_gap"] = _within(first, GAP_MIN, GAP_MAX)
        out["total"] = _within((took[-1] - sent).total_seconds(), 0, WAIT_MAX)  # type: ignore[operator]
    if gaps:
        out["longest_gap"] = _within(max(gaps), 0, WAIT_MAX)
    named = [
        ("no_date", sent is None),
        ("no_hops", not took),
        ("future_date", (first is not None and first < -SKEW) or late),
        ("held_back", first is not None and first > LONG),
        ("out_of_order", out["order"] == "out_of_order"),
        ("long_gap", bool(gaps) and max(gaps) > LONG),
        ("odd_hour", sent is not None and sent.hour in ODD),
    ]
    return out | {"flags": [name for name, there in named if there] or ["none"]}


def with_burst(timing: dict[str, Any], near: int) -> dict[str, Any]:
    """The timing with how many other applications arrived in its window (asked of Ada, others.py)."""
    flags = [f for f in timing["flags"] if f not in ("none", "burst")] + (["burst"] if near >= BURST else [])
    return timing | {"burst": min(near, 20), "flags": flags or ["none"]}


def found(timing: dict[str, Any]) -> list[str]:
    """What the timing check found, each in a sentence (none: nothing a person would want to know)."""
    return [SAID[f].format(n=timing["burst"]) for f in timing["flags"] if f in SAID]
