"""The Resume Screener's writing checks: how each part of an application was written, measured
apart, since a person who had one part polished leaves the others in their own hand. For the email, the cover
letter and the resume: the stock phrases of generated applications, how unevenly long the sentences are, the
contractions and exclamation marks and small slips a person leaves (a lower-case "i", doubled spaces or marks, a
sentence begun without its capital), its long dashes and its specifics; then how far the parts stand apart on
each. Counts, not a model (signals.py measures the application as one): Ada learns what they mean."""

import re
from typing import Any

from . import signals

CONTRACTION: re.Pattern[str] = re.compile(rf"\b\w+['{chr(0x2019)}](?:t|s|m|re|ve|ll|d)\b", re.I)
SLIP: re.Pattern[str] = re.compile(r"(?<![\w'])i(?![\w'])|  +\S|[!?]{2,}|\.\.\.|[.!?] +[a-z]| ,")
FIRST: re.Pattern[str] = re.compile(r"\b(?:I|my|me|I'm|I've)\b")
SHORT: int = 25  # words: under this a part says too little of how it was written
APART: tuple[str, ...] = ("stock", "burst", "contractions", "slips", "sentence")


def part(said: str) -> dict[str, Any]:
    """One part's measures, each a small whole number (per thousand words where it is a rate)."""
    words = len(signals.WORD.findall(said))
    lower = said.lower()
    sentences = [n for n in (len(signals.WORD.findall(s)) for s in signals.SENTENCE.split(said)) if n > 2]

    def rate(n: int, cap: int) -> int:
        return signals._per_k(n, words, cap)

    return {
        "words": min(words, 2000),
        "stock": rate(sum(lower.count(s) for s in signals.STOCK), 80),
        "burst": signals.burstiness(said),
        "sentence": min(60, round(sum(sentences) / len(sentences))) if sentences else 0,
        "contractions": rate(len(CONTRACTION.findall(said)), 80),
        "exclaims": rate(said.count("!"), 40),
        "slips": rate(len(SLIP.findall(said)), 80),
        "first": rate(len(FIRST.findall(said)), 120),
        "dashes": rate(said.count("—"), 20),
        "specifics": rate(len(signals.NUMBER.findall(signals.YEAR.sub(" ", signals.PHONE.sub(" ", said)))), 100),
    }


def whole(email: str, letter: str, resume: str) -> dict[str, Any]:
    """Each part measured, and `apart`: on each measure, how far the parts that say enough stand from each other."""
    parts = {"email": part(email), "letter": part(letter), "resume": part(resume)}
    said = [p for p in parts.values() if p["words"] >= SHORT]
    apart = {m: max(p[m] for p in said) - min(p[m] for p in said) if len(said) > 1 else 0 for m in APART}
    return parts | {"apart": apart}
