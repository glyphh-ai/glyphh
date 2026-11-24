"""Run the checks of docs/checks.md against your own Ada Cloud account (GLYPHH_API_KEY; GLYPHH_ADA_URL when it is
not https://ada.glyphh.ai). Each check makes its own models, named `check...`; delete them after.

    python run.py carried-over --corpus DIR
    python run.py others-design --corpus DIR      then     python run.py others-heldout --corpus DIR
    python run.py together-design                 then     python run.py together-heldout
    python run.py timing-learns
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE: Path = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "skills" / "screen-application" / "scripts"), str(HERE)]

import checks  # noqa: E402


async def ada(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = os.environ.get("GLYPHH_ADA_URL", "https://ada.glyphh.ai").rstrip("/") + path
    heads = {"authorization": f"Bearer {os.environ['GLYPHH_API_KEY']}", "content-type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data, heads, method=method)) as got:
                return json.loads(got.read())
        except urllib.error.HTTPError as err:
            if err.code != 429:  # the plan's rate: wait as it says, ask again
                raise
            time.sleep(float(err.headers.get("retry-after", "1")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("check")
    parser.add_argument("--corpus")
    args = parser.parse_args()
    name, _, mode = args.check.partition("-")
    corpus = Path(args.corpus) if args.corpus else None
    run = {
        "carried": lambda: checks.carried_over(ada, corpus),
        "others": lambda: checks.against_the_others(ada, corpus, mode),
        "together": lambda: checks.arriving_together(ada, mode),
        "timing": lambda: checks.timing_learns(ada),
    }[name]
    print(json.dumps(asyncio.run(run()), indent=1))


if __name__ == "__main__":
    main()
