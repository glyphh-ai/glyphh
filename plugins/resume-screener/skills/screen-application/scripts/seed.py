"""Set the Resume Screener up in your own Ada account, through the Glyphh SDK (pip install glyphh; `glyphh login`,
or GLYPHH_API_KEY): make its six models and load the examples that ship with the plugin.

    python seed.py

It can be run again at any time: a model that is there is left as it is, an example already held is replaced by
itself (each has its own id), and learning is run again.

What is loaded where (models/examples, one case a line):
- fit: 1,980 examples with their fit (strong, borderline, poor); then Ada's own learning is run.
- made: the same 1,980 with how much of each was generated (some, mostly, fully); then learning.
- others: the same 1,980, held so new applications are compared with them.
- files, timing, greenhouse: nothing. They start empty and learn from your answers alone.

Every example is a generated, fictional application: a program wrote it, and no real person is in it."""

import argparse
import gzip
import json
from typing import Any

from screener import steps

CHUNK: int = 500
EXAMPLES = steps.MODELS / "examples"


def examples(name: str) -> list[dict[str, Any]]:
    """The model's shipped examples, each {data, outcome}; none for a model that starts empty."""
    path = EXAMPLES / f"{name}.jsonl.gz"
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def setup(ada: Any, prefix: str = steps.PREFIX, say: Any = print) -> None:
    """`ada` is the SDK's client (glyphh.Ada)."""
    have = {m.name for m in ada.models()}
    for name, model in steps.models().items():
        full = prefix + name
        if full in have:
            say(f"{full}: already there")
        else:
            ada.create_model(full, model["spec"] | {"name": full})
            say(f"{full}: made")
        cases = examples(name)
        for at in range(0, len(cases), CHUNK):
            ada.model(full).record_many(cases[at : at + CHUNK])
        if cases:
            say(f"{full}: {len(cases)} examples loaded")
        if cases and model["learn"]:
            ada.model(full).learn()
            say(f"{full}: learned")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prefix", default=steps.PREFIX, help="what your models' names begin with")
    args = parser.parse_args()
    from glyphh import Ada

    setup(Ada(), args.prefix)


if __name__ == "__main__":
    main()
