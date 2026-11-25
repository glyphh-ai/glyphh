"""protocol.py — how the four agents speak to each other IN glyphs.

Owner: courier. Spec: LANGUAGE.md, section "Protocol". Built on
lexicon's language.py: an envelope is an ordinary sentence of the
language, so LX.decode can read it too.

THE ENVELOPE (one glyph per message)

    MSG = lx.encode({ "proto":    "proto_v1",          # the handshake word
                      "from":     "<agent>",
                      "to":       "<agent>|all",
                      "act":      "<speech act>",      # ACTS below
                      "content":  <any meaning or glyph>,
                      "reply_to": <parent MSG glyph>,  # optional
                      "thread":   <Strand state of the conversation so far> })

- content is any meaning lexicon's grammar builds (word, frame, list,
  concept) or a raw glyph (a fact from memory, a conclusion from
  reasoner, a whole conversation).
- reply_to carries the parent's GLYPH, not an id: the receiver unbinds
  it and picks the nearest message it has seen.
- thread carries Strand(the conversation up to and including the
  parent).state(): a receiver that missed the parent can still tell
  which conversation this belongs to.
- validity: unbind(MSG, role proto) must resemble word proto_v1. A
  foreign vocabulary (other seed) or a garbled glyph measures ~0 there
  and is rejected before any field is trusted.
- fidelity: the receiver re-encodes what it read and measures
  sim(re-encoding, MSG). ~1.0 = everything was read; lower = parts of
  the message were not recovered (garbled, or words it doesn't know).
- a conversation is itself a glyph: Conversation(...).state(). It can
  be the content of another message, or `events` in a Space.

APPLICATION LAYER (on channel.py): send(), inbox(), threads(),
conversation_of(). CLI: shared/say.py.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

_HERE = Path(__file__).resolve().parent
for p in (_HERE, _HERE.parent):           # language.py, channel.py
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from language import LX, Lexicon, render  # noqa: E402
from glyphh_kernel import Strand, bind, roll, sim  # noqa: E402

PROTO = "proto_v1"
DIM = LX.dim
ACTS = ("tell", "ask", "answer", "propose", "agree", "disagree", "ack",
        "correct", "done")
AGENTS = ("lexicon", "courier", "memory", "reasoner", "all", "orchestrator")
ENVELOPE_ROLES = ("proto", "from", "to", "act", "content", "reply_to", "thread")

# Thresholds (noise std between random glyphs at dim 4096 = 1/64 = 0.016).
VALID_MIN = 0.12     # handshake below this -> foreign / garbled   (>7 sigma)
FIELD_MIN = 0.08     # a field below this is unreadable            (5 sigma)
MARGIN_MIN = 0.03    # best candidate must beat the runner-up by this
CONCEPT_SHARE = 0.6  # a named-concept content must reach this x handshake sim


# ── building ────────────────────────────────────────────────────────
@dataclass
class Message:
    sender: str
    to: str
    act: str
    content: Any                         # meaning or np.ndarray
    reply_to: Optional[np.ndarray] = None
    thread: Optional[np.ndarray] = None

    def meaning(self) -> Dict[str, Any]:
        if self.act not in ACTS:
            raise ValueError(f"unknown speech act {self.act!r}; one of {ACTS}")
        m = {"proto": PROTO, "from": self.sender, "to": self.to,
             "act": self.act, "content": self.content}
        if self.reply_to is not None:
            m["reply_to"] = np.asarray(self.reply_to, dtype=np.int8)
        if self.thread is not None:
            m["thread"] = np.asarray(self.thread, dtype=np.int8)
        return m

    def glyph(self, lx: Lexicon = LX) -> np.ndarray:
        return lx.encode(self.meaning())


# ── reading ─────────────────────────────────────────────────────────
def cleanup(noisy: np.ndarray, candidates: Dict[str, np.ndarray]
            ) -> Tuple[Optional[str], float, float]:
    """Nearest candidate: (name, sim, margin over runner-up)."""
    if not candidates:
        return None, 0.0, 0.0
    names = list(candidates)
    M = np.stack([candidates[n] for n in names]).astype(np.float32)
    s = (M @ noisy.astype(np.float32)) / len(noisy)
    order = np.argsort(s)[::-1]
    best = float(s[order[0]])
    second = float(s[order[1]]) if len(order) > 1 else 0.0
    return names[order[0]], best, best - second


@dataclass
class Decoded:
    valid: bool
    proto_sim: float
    fields: Dict[str, Tuple[Optional[str], float]] = field(default_factory=dict)
    content: Any = None            # decoded content meaning (None = unread)
    content_glyph: Optional[np.ndarray] = None   # unbound, unrolled (noisy)
    fidelity: float = 0.0
    reason: str = ""

    def get(self, name: str) -> Optional[str]:
        v = self.fields.get(name)
        return v[0] if v else None

    def summary(self) -> str:
        if not self.valid:
            return f"REJECT ({self.reason}; proto_sim={self.proto_sim:+.3f})"
        f = " ".join(f"{k}={v[0]}({v[1]:.2f})" for k, v in self.fields.items())
        return (f"OK proto={self.proto_sim:.2f} fidelity={self.fidelity:.2f} "
                f"| {f} | content={render(self.content)}")


def _slot(g: np.ndarray, role: str, lx: Lexicon) -> np.ndarray:
    return bind(g, lx.role(role))


def decode(g: np.ndarray, lx: Lexicon = LX,
           known_msgs: Optional[Dict[str, np.ndarray]] = None,
           known_threads: Optional[Dict[str, np.ndarray]] = None,
           read_content: bool = True, depth: int = 2) -> Decoded:
    """Read a message from its glyph alone (never from the text).

    known_msgs: message glyphs the receiver has seen (for reply_to).
    known_threads: conversation states it knows (for thread).
    """
    g = np.asarray(g, dtype=np.int8)
    if g.shape != (lx.dim,):
        return Decoded(False, 0.0, reason=f"wrong shape {g.shape}")
    ps = sim(_slot(g, "proto", lx), lx.word(PROTO))
    if ps < VALID_MIN:
        return Decoded(False, ps, reason="no handshake: foreign seed, "
                       "garbled, or not an envelope")
    d = Decoded(True, ps)
    agents = {a: lx.word(a) for a in AGENTS}
    acts = {a: lx.word(a) for a in ACTS}
    for fld, book in (("from", agents), ("to", agents), ("act", acts)):
        name, s, m = cleanup(_slot(g, fld, lx), book)
        d.fields[fld] = (name if s >= FIELD_MIN and m >= MARGIN_MIN else None, s)
    for fld, book in (("reply_to", known_msgs), ("thread", known_threads)):
        if book:
            name, s, m = cleanup(roll(_slot(g, fld, lx), -1), book)
            if s >= FIELD_MIN and m >= MARGIN_MIN:
                d.fields[fld] = (name, s)
    raw = _slot(g, "content", lx)
    d.content_glyph = roll(raw, -1)
    if read_content:
        lx.refresh()
        # Candidate readings of the content slot, judged by how well each
        # re-encoding explains the received glyph (fidelity). A named
        # concept must be about as strong as the handshake slot (every
        # envelope slot carries the same share of the bundle): a concept
        # that merely SHARES a slot or two with the real content measures
        # a fraction of that and used to win a plain nearest-name cleanup
        # (live audit, 5 of 17 messages misread before this rule).
        word, s = lx.cleanup(raw, 1)[0]
        readings = []
        if s >= max(FIELD_MIN, CONCEPT_SHARE * ps):
            readings.append((word, expand(word, lx) if word in lx.concepts else word))
        anon = lx.decode(d.content_glyph, depth=depth)
        if anon is not None:
            readings.append((anon, expand(anon, lx)))
        if readings:
            best = max(readings, key=lambda r: _fidelity(
                g, d, lx, known_msgs, known_threads, content_as_sent=r[0]))
            d.content = best[1]
            d._sent_content = best[0]
    d.fidelity = _fidelity(g, d, lx, known_msgs, known_threads)
    return d


def expand(m: Any, lx: Lexicon = LX, _depth: int = 0) -> Any:
    """Replace concept names by their definitions, recursively (exact:
    the definitions are in the shared codebook)."""
    if _depth > 32:
        return m
    if isinstance(m, str) and m in lx.concepts and \
            not lx.concepts[m].get("atomic"):
        return expand(lx.concepts[m]["meaning"], lx, _depth + 1)
    if isinstance(m, dict):
        return {k: expand(v, lx, _depth + 1) for k, v in m.items()}
    if isinstance(m, list):
        return [expand(v, lx, _depth + 1) for v in m]
    return m


def chunked(content: Any, lx: Lexicon = LX) -> Any:
    """Name a composite content (and everything nested in it) as
    content-hash concepts in the shared codebook, so it survives the
    envelope at any size/depth. Glyph-neutral for nested parts; the
    content slot then holds one clean concept glyph."""
    if isinstance(content, (dict, list, tuple)):
        return lx.chunk(content, whole=True)
    return content


def _fidelity(g, d: Decoded, lx: Lexicon, known_msgs, known_threads,
              content_as_sent: Any = None) -> float:
    """Re-encode what was read; how much of the received glyph does it
    explain? Unreadable parts are left out, so they lower the score."""
    m: Dict[str, Any] = {"proto": PROTO}
    for fld in ("from", "to", "act"):
        if d.get(fld):
            m[fld] = d.get(fld)
    sent = content_as_sent if content_as_sent is not None else \
        getattr(d, "_sent_content", d.content)
    if sent is not None:
        m["content"] = sent
    if d.get("reply_to"):
        m["reply_to"] = known_msgs[d.get("reply_to")]
    if d.get("thread"):
        m["thread"] = known_threads[d.get("thread")]
    try:
        return sim(lx.encode(m), g)
    except Exception:
        return 0.0


# ── conversations ───────────────────────────────────────────────────
class Conversation:
    """A thread: ordered message glyphs. state() is the conversation as
    one glyph (kernel Strand; recent turns dominate, order matters)."""

    def __init__(self, msgs: Optional[Sequence[np.ndarray]] = None,
                 decay: float = 0.7):
        self.strand = Strand(list(msgs or []))
        self.decay = decay

    def add(self, g: np.ndarray) -> "Conversation":
        self.strand.append(g)
        return self

    def state(self) -> np.ndarray:
        return self.strand.state(self.decay)

    def turn(self, age: int) -> np.ndarray:
        """Noisy view of the turn `age` steps back (0 = latest)."""
        return roll(self.state(), -age)

    def __len__(self) -> int:
        return len(self.strand)


# ── application layer on the channel ────────────────────────────────
KIND = "glyph-msg"
CONTENT_BUDGET = 4          # flat slots readable exactly in a bare envelope
CONTENT_BUDGET_LINKED = 3   # ... with reply_to + thread bound in


def _slots(m: Any) -> int:
    return len(m) if isinstance(m, (dict, list, tuple)) else 1


def _nested(m: Any) -> bool:
    vals = m.values() if isinstance(m, dict) else m
    return any(isinstance(v, (dict, list, tuple, np.ndarray)) for v in vals)


def _channel():
    import channel
    return channel


def envelopes(since: float = 0.0) -> List[dict]:
    """Every channel line that carries a glyph, oldest first."""
    return [m for m in _channel().read(since=since) if "glyph" in m]


def resolve(msgs: Optional[List[dict]] = None, lx: Lexicon = LX,
            read_content: bool = True) -> List[Tuple[dict, Decoded]]:
    """Decode every glyph on the channel FROM THE GLYPH ONLY, resolving
    reply_to against the glyphs seen before it and thread against the
    conversations built so far. Returns [(line, Decoded)]."""
    msgs = envelopes() if msgs is None else msgs
    seen: Dict[str, np.ndarray] = {}
    parent_of: Dict[str, Optional[str]] = {}
    out = []
    for line in msgs:
        key = repr(line["ts"])
        threads = {k: _conv_state(k, seen, parent_of) for k in seen}
        d = decode(line["glyph"], lx, known_msgs=seen or None,
                   known_threads=threads or None, read_content=read_content)
        # any glyph can be replied to (a bare glyph is a one-turn thread)
        seen[key] = line["glyph"]
        parent_of[key] = d.get("reply_to") if d.valid else None
        out.append((line, d))
    return out


def _chain(key: str, parent_of: Dict[str, Optional[str]]) -> List[str]:
    chain, k = [], key
    while k is not None and k not in chain:
        chain.append(k)
        k = parent_of.get(k)
    return chain[::-1]


def _conv_state(key, seen, parent_of) -> np.ndarray:
    return Conversation([seen[k] for k in _chain(key, parent_of)]).state()


def send(sender: str, to: str, act: str, content: Any,
         reply_ts: Optional[float] = None, text: str = "",
         lx: Optional[Lexicon] = None, chunk: Optional[bool] = None,
         **extra) -> dict:
    """Build the envelope glyph and post it. If reply_ts is given, the
    parent glyph and the thread state (conversation up to the parent)
    are taken from the channel and bound in."""
    lx = lx or Lexicon(author=sender)
    reply = thread = None
    if reply_ts is not None:
        res = resolve(read_content=False, lx=lx)
        by_ts = {repr(l["ts"]): (l, d) for l, d in res}
        key = repr(float(reply_ts))
        if key not in by_ts:
            raise KeyError(f"no glyph message at ts={reply_ts}")
        reply = by_ts[key][0]["glyph"]
        parent_of = {k: (d.get("reply_to") if d.valid else None)
                     for k, (l, d) in by_ts.items()}
        seen = {k: l["glyph"] for k, (l, d) in by_ts.items()}
        thread = _conv_state(key, seen, parent_of)
    budget = CONTENT_BUDGET_LINKED if reply is not None else CONTENT_BUDGET
    if chunk is None:   # auto: chunk when the content is over budget or nested
        chunk = isinstance(content, (dict, list, tuple)) and (
            _slots(content) > budget or _nested(content))
    sent = chunked(content, lx) if chunk else content
    msg = Message(sender, to, act, sent, reply, thread)
    g = msg.glyph(lx)
    receipt = {k: v for k, v in Message(sender, to, act, content).meaning().items()
               if not isinstance(v, np.ndarray)}
    if isinstance(content, np.ndarray):
        receipt["content"] = "<glyph>"
    return _channel().post(
        sender, to, text or f"[{act}] {render(receipt.get('content'))}",
        glyph=g, kind=KIND, proto=PROTO, meaning=json.dumps(receipt),
        reply_ts=reply_ts, **extra)


def inbox(me: str, since: float = 0.0, lx: Lexicon = LX
          ) -> List[Tuple[dict, Decoded]]:
    """Messages addressed (by their GLYPH) to me or all, newer than since."""
    return [(l, d) for l, d in resolve(lx=lx)
            if l["ts"] > since and d.valid and d.get("to") in (me, "all")]


def threads(lx: Lexicon = LX) -> Dict[str, List[List[str]]]:
    """Conversations reconstructed from glyph reply links: root ts ->
    its branches, each an ordered chain of message ts from the root to a
    leaf (two answers to one ask are two branches of one conversation)."""
    res = resolve(lx=lx, read_content=False)
    parent_of = {repr(l["ts"]): (d.get("reply_to") if d.valid else None)
                 for l, d in res}
    parents = {p for p in parent_of.values() if p}
    out: Dict[str, List[List[str]]] = {}
    for leaf, p in parent_of.items():
        if leaf in parents or p is None:
            continue
        chain = _chain(leaf, parent_of)
        out.setdefault(chain[0], []).append(chain)
    return out


def conversation_of(ts: float, lx: Lexicon = LX) -> Tuple[List[str], np.ndarray]:
    """The conversation ending at message ts, and its glyph."""
    res = resolve(lx=lx, read_content=False)
    parent_of = {repr(l["ts"]): (d.get("reply_to") if d.valid else None)
                 for l, d in res}
    seen = {repr(l["ts"]): l["glyph"] for l, d in res}
    chain = _chain(repr(float(ts)), parent_of)
    return chain, Conversation([seen[k] for k in chain]).state()


def audit(lx: Lexicon = LX) -> Dict[str, Any]:
    """Decode every envelope on the channel from its glyph and compare
    with the sender's receipt (the `meaning` JSON on the line). This is
    the live decode-accuracy measurement of the protocol."""
    res = resolve(lx=lx)
    stats = {"lines_with_glyph": len(res), "envelopes": 0, "bare_glyphs": 0,
             "fields": {}, "content_exact": [0, 0], "reply_to": [0, 0],
             "mismatches": []}
    for l, d in res:
        if not d.valid:
            stats["bare_glyphs"] += 1
            continue
        stats["envelopes"] += 1
        if "meaning" not in l:
            continue
        want = json.loads(l["meaning"])
        for fld in ("from", "to", "act"):
            ok, n = stats["fields"].get(fld, [0, 0])
            hit = d.get(fld) == want.get(fld)
            stats["fields"][fld] = [ok + hit, n + 1]
            if not hit:
                stats["mismatches"].append((l["ts"], fld, want.get(fld), d.get(fld)))
        if want.get("content") != "<glyph>":
            want["content"] = expand(want.get("content"), lx)   # receipts may carry c: names
            hit = d.content == want.get("content")
            stats["content_exact"][0] += hit
            stats["content_exact"][1] += 1
            if not hit:
                stats["mismatches"].append((l["ts"], "content", want.get("content"),
                                            d.content))
        if l.get("reply_ts") is not None:
            hit = d.get("reply_to") == repr(float(l["reply_ts"]))
            stats["reply_to"][0] += hit
            stats["reply_to"][1] += 1
            if not hit:
                stats["mismatches"].append((l["ts"], "reply_to", l["reply_ts"],
                                            d.get("reply_to")))
    return stats


def conversations(lx: Lexicon = LX) -> Dict[str, np.ndarray]:
    """Every conversation branch on the channel as a glyph: leaf ts ->
    Conversation(root..leaf).state(). Also every prefix, so a summary sent
    mid-conversation is recognised too."""
    res = resolve(lx=lx, read_content=False)
    parent_of = {repr(l["ts"]): (d.get("reply_to") if d.valid else None)
                 for l, d in res}
    seen = {repr(l["ts"]): l["glyph"] for l, d in res}
    return {k: Conversation([seen[x] for x in _chain(k, parent_of)]).state()
            for k in seen if parent_of.get(k)}


def which_conversation(g: np.ndarray, lx: Lexicon = LX
                       ) -> Tuple[Optional[str], float, float]:
    """A message whose CONTENT is a conversation glyph: which one on the
    channel is it? -> (leaf ts, sim, margin)."""
    d = decode(g, lx, read_content=False)
    if not d.valid:
        return None, 0.0, 0.0
    return cleanup(d.content_glyph, conversations(lx))
