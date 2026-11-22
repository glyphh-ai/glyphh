"""What an application's words show of how it was written, for the Resume Screener's `made` gate (how much of it was
generated) and `source` gate: counts, not a model. Ada learns from the person's precedents what these counts mean
for them; this only measures. Stock phrases (the stock words of generated job applications) per thousand words and
which ones, how evenly long its sentences are (people's vary more), how many specific numbers it gives, its long
dashes, and its links."""

import re
import statistics
from typing import Any

STOCK: tuple[str, ...] = (
    *("i am writing to express", "keen interest", "ideal candidate", "proven track record", "results-driven"),
    *("passionate about", "leverag", "fast-paced", "welcome the opportunity", "dynamic team", "thrive in"),
    *("spearhead", "cross-functional", "detail-oriented", "impactful", "align perfectly", "unique blend"),
    *("eager to bring", "delve", "robust and scalable", "commitment to excellence", "hit the ground running"),
    *("synergy", "tapestry", "testament to", "seamless", "cutting-edge", "innovative solutions", "furthermore"),
    *("moreover", "i am excited to apply", "valuable asset", "strong foundation", "foster", "elevate", "embark"),
    *("multifaceted", "pivotal", "meticulous", "drive results", "wealth of experience", "honed my skills"),
)
WORD: re.Pattern[str] = re.compile(rf"[A-Za-z][A-Za-z'{chr(0x2019)}-]*")  # a word, its apostrophes either way
NUMBER: re.Pattern[str] = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|k\b|ms\b|kb\b)?", re.I)
SENTENCE: re.Pattern[str] = re.compile(r"[.!?\n]+")
LINK: re.Pattern[str] = re.compile(r"https?://", re.I)
YEAR: re.Pattern[str] = re.compile(r"\b(?:19|20)\d{2}\b")
PHONE: re.Pattern[str] = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def _per_k(n: int, words: int, cap: int) -> int:
    return min(cap, round(1000 * n / max(words, 50)))


def burstiness(said: str) -> int:
    """How unevenly long its sentences are: their lengths' spread over their mean, times 100 (0: all one length)."""
    lengths = [len(WORD.findall(s)) for s in SENTENCE.split(said)]
    lengths = [n for n in lengths if n > 2]
    if len(lengths) < 3:
        return 50
    return min(100, round(100 * statistics.pstdev(lengths) / statistics.mean(lengths)))


def measured(body: str, resume: str) -> dict[str, Any]:
    said = f"{body}\n{resume}"
    lower = said.lower()
    words = len(WORD.findall(said))
    tells = sorted({s for s in STOCK if s in lower})
    stock = sum(lower.count(s) for s in STOCK)
    specifics = len(NUMBER.findall(YEAR.sub(" ", PHONE.sub(" ", said))))  # dates and phones are not specifics
    return {
        "stock_per_k": _per_k(stock, words, 80),
        "tells": tells[:12] or ["none"],
        "burstiness": burstiness(body or resume),
        "specifics_per_k": _per_k(specifics, words, 100),
        "dashes_per_k": _per_k(said.count("—"), words, 20),
        "links": min(30, len(LINK.findall(body))),
        "words": words,
    }
