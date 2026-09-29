"""Demo: the codebook's concept structure -> KB part_of facts -> reasoner's
glyph closure -> derived facts, each checked against the definitions.

    python3 agents/lexicon/demo_closure.py
"""
import sys
from pathlib import Path

A = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(A / "shared"), str(A / "lexicon")]
from knowledge import KB            # noqa: E402
from reason import Frames, closure  # noqa: E402
from concepts import reproduce      # noqa: E402
from language import Lexicon        # noqa: E402

kb, lx = KB(), Lexicon(author="lexicon")
facts = [(c.subject, "part_of", c.value) for c in kb.all_claims("lexicon")
         if c.relation == "part_of"]
derived = closure(Frames(facts), "part_of")
ok = sum(reproduce(d.fact[0], d.fact[2], lx) == d.fact[2] for d in derived)
print(f"{len(facts)} told part_of facts -> {len(derived)} derived by closure "
      f"(depth {sorted({d.depth for d in derived})}); "
      f"{ok}/{len(derived)} reproduced from the codebook definitions")
