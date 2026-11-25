"""The tests import the skill's own code (skills/screen-application/scripts) and the test helpers beside them."""

import sys
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "skills" / "screen-application" / "scripts"), str(HERE), str(HERE.parent / "checks")]
