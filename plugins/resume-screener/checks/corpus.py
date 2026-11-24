"""The applicant corpus as the checks and the examples' build read it: a folder with `manifest.jsonl` (one
generated applicant a line: id, split, fit, generated) and `files/<id>/email.eml` (the application as an email with
its cover letter and resume attached). The corpus itself is not in this repository; what ships is the train split
as the models' cases (models/examples, built by build_examples.py). Each row is read by the same code a screening
uses, so a precedent and a new application are read alike.

    python corpus.py DIR      build models/examples from the corpus's train split"""

import gzip
import json
import sys
from pathlib import Path
from typing import Any

HERE: Path = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "skills" / "screen-application" / "scripts")]

from screener import mail, steps  # noqa: E402

EXAMPLES: Path = steps.MODELS / "examples"


def rows(corpus: Path, split: str = "train") -> list[dict[str, Any]]:
    lines = (corpus / "manifest.jsonl").read_text().splitlines()
    return [row for row in map(json.loads, lines) if row["split"] == split]


def precedents(corpus: Path, row: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    """One row as each seeded model's precedent ({model: {data, outcome}}); None when the sender checks refuse it.
    The `others` model holds it without its arrival time: the corpus's emails were all written by one program in
    one sitting and say nothing true about timing."""
    made = steps.read(mail.read((corpus / "files" / row["id"] / "email.eml").read_bytes(), row["id"]))
    if "refused" in made:
        return None
    held = {part: case for part, case in made["others"].items() if part != "when"}
    cases = steps.cases(steps.compare(made, {}))
    return {
        "fit": {"data": cases["fit"], "outcome": row["fit"]},
        "made": {"data": cases["made"], "outcome": row["generated"]},
        "others": {"data": held, "outcome": "alone"},
    }


def build(corpus: Path) -> dict[str, int]:
    """The train split written as each model's examples: one case a line, gzipped, the same bytes every time."""
    made: dict[str, list[str]] = {"fit": [], "made": [], "others": []}
    for row in sorted(rows(corpus, "train"), key=lambda r: r["id"]):
        for name, case in (precedents(corpus, row) or {}).items():
            made[name].append(json.dumps(case, sort_keys=True, separators=(",", ":")))
    EXAMPLES.mkdir(exist_ok=True)
    for name, lines in made.items():
        with gzip.GzipFile(EXAMPLES / f"{name}.jsonl.gz", "wb", mtime=0) as out:
            out.write(("\n".join(lines) + "\n").encode())
    return {name: len(lines) for name, lines in made.items()}


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
