"""What a PDF file itself says (filefacts.py): the program that made it and the one that wrote the file,
its author, when it was made and last changed, how many times it was saved over (each save appends an end-of-file
mark), its fonts, and the text a reader would not see: drawn invisibly (text rendering mode 3), in white, or
smaller than a reader can read. Counting is all it does; a file it cannot walk says so by raising ValueError."""

import io
import re
from typing import Any

TINY: float = 4.0  # points: under this a reader does not see words
WHITE: dict[str, tuple[float, ...]] = {"rg": (1, 1, 1), "g": (1,), "k": (0, 0, 0, 0)}
SHOWN: frozenset[str] = frozenset(("Tj", "TJ", "'", '"'))
STAMP: re.Pattern[str] = re.compile(r"(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")
SUBSET: re.Pattern[str] = re.compile(r"^[A-Z]{6}\+")


def stamp(said: Any) -> str:
    """A PDF date (D:20261122114327-06'00') as 2026-11-22T11:43:27; empty when it is not one."""
    found = STAMP.search(str(said or ""))
    if not found:
        return ""
    y, mo, d, h, mi, s = (g or "00" for g in found.groups())
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}"


def _letters(operands: list[Any]) -> int:
    """How many characters a text-showing operator draws."""
    shown = operands[-1] if operands else ""
    parts = shown if isinstance(shown, list) else [shown]
    return sum(len(p) for p in parts if isinstance(p, str | bytes))


def unseen(operations: list[tuple[list[Any], Any]]) -> dict[str, int]:
    """The characters of a page's content drawn invisibly, in white, and tiny."""
    out = {"hidden": 0, "white": 0, "tiny": 0}
    mode, white, size = 0, False, 12.0
    for operands, operator in operations:
        op = operator.decode() if isinstance(operator, bytes) else str(operator)
        if op == "Tr":
            mode = int(operands[0])
        elif op in WHITE:
            white = tuple(float(x) for x in operands) == WHITE[op]
        elif op == "Tf":
            size = float(operands[1])
        elif op in SHOWN:
            n = _letters(operands)
            out["hidden"] += n if mode == 3 else 0
            out["white"] += n if white and mode != 3 else 0
            out["tiny"] += n if 0 < size < TINY and mode != 3 else 0
    return out


def facts(data: bytes) -> dict[str, Any]:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream

    reader = PdfReader(io.BytesIO(data))
    meta = reader.metadata or {}
    out: dict[str, Any] = {"hidden": 0, "white": 0, "tiny": 0}
    fonts: set[str] = set()
    for page in reader.pages[:20]:
        for font in ((page.get("/Resources") or {}).get("/Font") or {}).values():
            fonts.add(SUBSET.sub("", str(font.get_object().get("/BaseFont", "")).lstrip("/")))
        drawn = page.get_contents()  # none: an empty page
        for name, n in unseen(ContentStream(drawn, reader).operations if drawn is not None else []).items():
            out[name] += n
    return out | {
        "producer": str(meta.get("/Producer") or ""), "creator": str(meta.get("/Creator") or ""),
        "author": str(meta.get("/Author") or ""), "created": stamp(meta.get("/CreationDate")),
        "modified": stamp(meta.get("/ModDate")), "saves": max(1, data.count(b"%%EOF")),
        "fonts": sorted(f for f in fonts if f), "tracked": 0,
    }  # fmt: skip
