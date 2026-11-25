"""courier/live_stats.py -- measure the protocol on the REAL channel (read-only).
python3 courier/live_stats.py"""
import sys
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import channel  # noqa: E402
import language as L  # noqa: E402
import protocol as P  # noqa: E402

raw = list(channel.read())
msgs = P.inbox()
print(f"channel lines: {len(raw)}   with payload: {len(msgs)}")
print("status:", dict(Counter(m.status for m in msgs)))
env = [m for m in msgs if m.status in ("ok", "noisy")]
print("protocol messages by sender:", dict(Counter(m.sender for m in env)))
print("by act:", dict(Counter(m.act for m in env)))
print(f"text field == payload decode: {sum(m.text_matches for m in env)}/{len(env)}")
print(f"payload :from == channel from: {sum(m.from_matches for m in env)}/{len(env)}")
# reply-to: the channel line carries no re field, so compare the payload-decoded re
# with the id quoted in the human text (^m...) where present
chk = [(m, m.raw_text.split(":re ^")[1].split()[0].rstrip(")")) for m in env if ":re ^" in m.raw_text]
print(f"reply-to recovered from payload == id in text: {sum(m.re == t for m, t in chk)}/{len(chk)}")
ths = P.Thread.all(env)
multi = {k: t for k, t in ths.items() if len(t.messages) > 1}
tot = rec = 0
for t in multi.values():
    tv = t.vector()
    for i, m in enumerate(t.messages):
        tot += 1; rec += t.turn(tv, i)[0] is m
print(f"threads: {len(ths)} ({len(multi)} with replies); turns recovered from thread vectors: {rec}/{tot}")
facts = P.distill_all(msgs)
print(f"distilled facts: {len(facts)}  (from Q/A: {sum(1 for f in facts if f['asked_by'])}, "
      f"endorsed: {sum(1 for f in facts if f['endorsed'])}, disputed: {sum(1 for f in facts if f['disputed'])})")
for f in facts:
    if f["asked_by"] or f["endorsed"] or f["disputed"]:
        print("  ", L.show(f["fact"]), "src", f["src"], "asked_by", f["asked_by"],
              "endorsed", f["endorsed"], "disputed", f["disputed"])
profs = P.profiles(msgs)
print("route (query :subj protocol :rel ? ...):", [(a, round(s, 2)) for a, s in
      P.route({"subj": "protocol"}, profs)])
print("route (query :subj knowledge.py ...):", [(a, round(s, 2)) for a, s in
      P.route({"subj": "knowledge.py"}, profs)])
