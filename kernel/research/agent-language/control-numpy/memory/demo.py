"""demo.py -- the KB end to end, on a PRIVATE log + lexicon (touches nothing shared).
Run: python3 memory/demo.py"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
import knowledge as K  # noqa: E402
import language as L  # noqa: E402

lex = L.Lexicon(path=None)
kb = K.KB(Path(tempfile.mkdtemp()) / "kb.jsonl", lex=lex)


def show(q):
    a = kb.ask(*q)
    print(f"  ask {q}: {a.status:9s} obj={a.obj} trust={a.conf:.2f}")


print("1. lexicon tells a fact; nobody has graded it")
f1 = kb.tell("lexicon", "cat", "is_a", "mammal")
show(("cat", "is_a"))
print("   lexicon tries to grade its own fact:", end=" ")
try:
    kb.grade("lexicon", f1, True)
except ValueError as e:
    print("rejected:", e)
print("2. courier observes it independently and grades it")
kb.grade("courier", f1, True, how="observed")
show(("cat", "is_a"))
print("3. courier tells a false arithmetic claim with a check; memory re-runs the check")
f2 = kb.tell("courier", "7x9", "equals", "64", check="expr:7*9 == 64")
print("   reproduce ->", kb.reproduce("memory", f2))
show(("7x9", "equals"))
print("4. a sentence arrives as a channel payload and is ingested")
_, wire = L.say("(assert :subj moon :rel orbits :obj earth)", lex)
kb.ingest({"from": "reasoner", "payload": wire})
g = K.grade_meaning("lexicon", "moon", "orbits", "earth", True, "observed")
kb.ingest({"from": "lexicon", "payload": L.to_wire(L.encode(g, lex, persist=False))})
show(("moon", "orbits"))
print("5. the log line for that grade, decoded from its vector alone:")
import json  # noqa: E402
last = json.loads(kb.path.read_text().splitlines()[-1])
print("  ", L.show(L.decode(K._unb64(last["wire"]), lex)))
print("6. stats", kb.stats())
