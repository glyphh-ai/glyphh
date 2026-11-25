"""The Ada kernel every benchmark here measures: Glyphh's, not published. GLYPHH_KERNEL points at an ada-private
checkout (default: ../ada-private, beside this repo). load() refuses anything else — an older copy, a kernel without
its lexicon, or a lexicon that does not load — so a run can only ever measure the product."""

from __future__ import annotations

import functools
import os
import sys
import tomllib
from pathlib import Path

KERNEL = Path(os.environ.get("GLYPHH_KERNEL", Path(__file__).resolve().parents[1] / "ada-private")).resolve()
MIN_VERSION = (3, 11, 0)  # the kernel whose one model answers many questions (named outputs)
LEXICON_WORDS, LEXICON_FORMS = 77_817, 192_960  # WordNet 3.0 words, Moby word forms (ada-private/lexicon)


@functools.cache
def load():
    """glyphh_spec from the ada-private kernel, checked once: its version, its lexicon on disk, and the lexicon
    actually loaded. Exits with the reason otherwise; a benchmark of an older or partial kernel is not a benchmark
    of Ada."""
    need = ["glyphh_kernel.py", "glyphh_spec.py", "glyphh_lexicon.py", "lexicon/words.jsonl.gz", "lexicon/grammar.jsonl.gz", "pyproject.toml"]
    missing = [n for n in need if not (KERNEL / n).is_file()]
    if missing:
        sys.exit(f"{KERNEL} is not an ada-private checkout (missing {', '.join(missing)}); set GLYPHH_KERNEL")
    project = tomllib.loads((KERNEL / "pyproject.toml").read_text())["project"]
    version = tuple(int(p) for p in project["version"].split(".")[:3])
    if version < MIN_VERSION:
        sys.exit(f"{KERNEL} has kernel {project['version']}; Ada is {'.'.join(map(str, MIN_VERSION))} or later")
    sys.path.insert(0, str(KERNEL))
    import glyphh_lexicon
    import glyphh_spec

    words, forms = glyphh_lexicon.LEXICON.size()
    if (words, forms) != (LEXICON_WORDS, LEXICON_FORMS):
        sys.exit(f"the lexicon loaded {words} words and {forms} forms, not {LEXICON_WORDS} and {LEXICON_FORMS}")
    print(f"Ada: kernel {project['version']} from {KERNEL}, lexicon {words:,} words / {forms:,} forms", file=sys.stderr)
    return glyphh_spec
