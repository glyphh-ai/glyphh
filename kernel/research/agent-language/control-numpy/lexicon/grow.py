"""Grow the shared vocabulary from real channel traffic (owner: lexicon).

    python3 lexicon/grow.py            # report only (dry run)
    python3 lexicon/grow.py --adopt    # define the mined words in shared/dictionary.jsonl + announce them

1. read every payload on the channel and decode it with language.read_back (payload only);
2. mine sub-structures that recur in >= 2 messages and are >= 4 leaves;
3. report leaves before/after compression (the language getting shorter for what we say);
4. --adopt: define them, and post each definition ON THE CHANNEL as a (define ...) payload.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "shared")); sys.path.insert(0, str(ROOT))
import language as L  # noqa: E402
import dictionary as Dn  # noqa: E402
from channel import read, post  # noqa: E402


def corpus(lex):
    out = []
    for m in read():
        if "payload" not in m:
            continue
        r = L.read_back(m["payload"], lex)
        if r.kind in ("frame", "list") and r.meaning:
            out.append((m, r.meaning))
    return out


def main(adopt=False, min_count=2, min_leaves=4):
    lex = L.Lexicon()
    dic = Dn.Dictionary(lex=lex)
    rows = corpus(lex)
    means = [mm for _, mm in rows]
    print(f"channel payloads decoded as meanings: {len(means)}")
    # heard definitions are adopted first (the channel teaches the dictionary)
    def atoms_outside_defines():
        out = set()
        for _, mm in rows:
            if not (isinstance(mm, dict) and mm.get("act") == "define"):
                out.update(L.words_of(mm)[0])
        return out
    used = atoms_outside_defines()
    taught = [dic.learn_from(mm, by=m["from"], persist=adopt, in_use=used) for m, mm in rows]
    taught = [t for t in taught if t]
    if taught:
        print("learned from channel (define ...):", taught)
    cands = dic.mine(means, min_count=min_count, min_leaves=min_leaves, top=12)
    before = sum(L.leaf_count(mm) for mm in means)
    print(f"leaves in traffic before: {before}")
    for sv, c, s in cands:
        print(f"   saves {sv:>3} leaves, seen in {c} msgs: {L.show(s)}")
    tmp = Dn.Dictionary(path=None, lex=L.Lexicon(path=None))
    for n, e in dic.entries.items():
        tmp.define("x", n, e["def"], persist=False)
    tmp.adopt("lexicon", cands, persist=False)
    after = sum(L.leaf_count(tmp.compress(mm)) for mm in means)
    ok = all(tmp.expand(tmp.compress(mm)) == tmp.expand(mm) for mm in means)
    print(f"leaves after compression: {after}  ({100 * (before - after) / max(before, 1):.1f}% shorter), "
          f"expand(compress(m)) == m for all: {ok}")
    if adopt:
        for d in dic.adopt("lexicon", cands, persist=True):
            post("lexicon", "all", L.show(d), payload=L.to_wire(L.encode(d, lex)), kind="define")
        print(f"adopted; dictionary now has {len(dic)} words")
    return before, after, cands


if __name__ == "__main__":
    main(adopt="--adopt" in sys.argv)
