"""UserPromptSubmit: inject precedent relevant to the incoming prompt.

The doorbell of the memory: fast, deterministic, model-free. It rings
when the prompt lexically resembles stored experience — situations,
outcomes (wins AND vetoes, so contemplating a discredited approach
surfaces the veto), and user-defined aliases. It deliberately stops
short of semantic matching: importing an embedding model here would
re-import everything the kernel avoids (dependencies, drift,
non-determinism). Paraphrase recall is the agent's job — the skill
tells it to run real similarity queries; this hook only makes sure
memory is never silently absent when the words line up.

Matching, most to least certain: exact token, shared-prefix/stem
(fishing/fish, deployed/deploy), edit-distance-1 incl. transpositions (chirs/chris).
Situation tokens count more than outcome tokens. Aliases
(<memory>/aliases.json: {"angling": ["fishing"]}) let the writer add
synonyms without touching the stores.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import memory_dir, rows

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "at",
    "is", "are", "it", "this", "that", "with", "as", "be", "do", "can",
    "you", "your", "we", "our", "i", "me", "my", "please", "then",
    "now", "just", "also", "how", "what", "when", "why", "not", "no",
    "should", "would", "could", "will", "was", "were", "has", "have",
    "had", "does", "did", "his", "her", "their", "them", "they", "she",
    "there", "here", "about", "into", "over", "out", "let", "lets",
    "like", "need", "want", "get", "got", "make", "made", "use", "using",
    "used", "one", "some", "any", "all", "but", "if", "so", "up", "down",
}

# thresholds and weights of the scorer
EXACT, NEAR, FUZZY = 1.0, 0.8, 0.6      # match-quality tiers
SITUATION_W, OUTCOME_W = 1.0, 0.75      # where the stored token lives
THRESHOLD = 1.2                         # min score to ring the bell
MAX_INJECT = 3                          # top situations injected

_SUFFIXES = ("ing", "edly", "ed", "es", "s", "er", "ers", "ly")


def _split(text: str):
    """snake_case, camelCase, kebab-case, digits — all become words."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-z]{3,}", text.lower())


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[:-len(suffix)]
    return token


def tokens(text: str) -> set:
    return {t for t in _split(text) if t not in STOP_WORDS}


def _edit1(a: str, b: str) -> bool:
    """True when a and b are within one edit (sub/ins/del), both >= 5
    chars — cheap typo tolerance without false hits on short words."""
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        if sum(x != y for x, y in zip(a, b)) <= 1:
            return True
        # adjacent transposition (Damerau): 'chirs' -> 'chris'
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return (len(diff) == 2 and diff[1] == diff[0] + 1
                and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):  # b is longer by one: try deleting each char
        if b[:i] + b[i + 1:] == a:
            return True
    return False


def _match_quality(stored: str, prompt_tokens: set,
                   prompt_stems: set) -> float:
    if stored in prompt_tokens:
        return EXACT
    stem = _stem(stored)
    if stem in prompt_stems or stem in prompt_tokens:
        return NEAR
    for p in prompt_tokens:
        if (len(stored) >= 4 and len(p) >= 4
                and (p.startswith(stored) or stored.startswith(p))):
            return NEAR
        if _edit1(stored, p):
            return FUZZY
    return 0.0


def _load_aliases(mem: Path) -> dict:
    """aliases.json maps a surface form to canonical tokens:
    {"angling": ["fishing"], "postgres": ["database", "db"]}."""
    path = mem / "aliases.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        return {str(k).lower(): [str(v).lower() for v in vals]
                for k, vals in raw.items() if isinstance(vals, list)}
    except (json.JSONDecodeError, OSError):
        return {}


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    mem = memory_dir(data.get("cwd", "."))
    if mem is None:
        return
    prompt_tokens = tokens(data.get("prompt", ""))
    if not prompt_tokens:
        return
    for surface, canonicals in _load_aliases(mem).items():
        if surface in prompt_tokens:
            prompt_tokens |= set(canonicals)
    prompt_stems = {_stem(t) for t in prompt_tokens}

    wins = rows(mem / "wins.db")
    vetoes = rows(mem / "vetoes.db")
    if not wins and not vetoes:
        return

    # Group identical situations; collect their outcome vocabulary.
    grouped = defaultdict(lambda: {"wins": defaultdict(int), "vetoes": set()})
    for situation, outcome, _ in wins:
        grouped[json.dumps(situation, sort_keys=True)]["wins"][outcome] += 1
    for situation, outcome, _ in vetoes:
        grouped[json.dumps(situation, sort_keys=True)]["vetoes"].add(outcome)

    scored = []
    for key, entry in grouped.items():
        situation = json.loads(key)
        situation_tokens = set()
        for k, v in situation.items():
            situation_tokens |= tokens(str(k)) | tokens(str(v))
        outcome_tokens = set()
        for outcome in list(entry["wins"]) + sorted(entry["vetoes"]):
            outcome_tokens |= tokens(outcome)
        outcome_tokens -= situation_tokens

        score = sum(SITUATION_W * _match_quality(t, prompt_tokens, prompt_stems)
                    for t in situation_tokens)
        score += sum(OUTCOME_W * _match_quality(t, prompt_tokens, prompt_stems)
                     for t in outcome_tokens)
        if score >= THRESHOLD:
            scored.append((score, situation, entry))
    if not scored:
        return

    scored.sort(key=lambda x: -x[0])
    lines = ["glyphh memory hits for this prompt (lexical doorbell; run a "
             "similarity query for anything borderline):"]
    for score, situation, entry in scored[:MAX_INJECT]:
        parts = []
        if entry["wins"]:
            worked = ", ".join(
                f"{o} (x{n})" for o, n in
                sorted(entry["wins"].items(), key=lambda x: -x[1]))
            parts.append(f"worked: {worked}")
        if entry["vetoes"]:
            parts.append(f"VETOED: {', '.join(sorted(entry['vetoes']))}")
        lines.append(f"- {json.dumps(situation, sort_keys=True)} -> "
                     + "; ".join(parts))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
