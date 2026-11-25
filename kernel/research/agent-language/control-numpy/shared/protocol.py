"""protocol.py -- how agents speak to each other IN the language (owner: courier).

A MESSAGE is one meaning of shared/language.py, so one hypervector, so one
1024-byte payload on the channel:

    {act:     <speech act>            assert tell ask answer propose agree disagree
                                       ack grade define done query
     from:    <agent>                  to: <agent | all>
     check:   proto_v1                 protocol marker (a real message carries it)
     conf:    conf_hi|conf_mid|conf_lo (optional)
     re:      <id of parent message>   embedded vector, not a vocab word (optional)
     thread:  <id of root message>     embedded vector (optional; root = own id)
     content: <any meaning>}           the thing said

IDs are content-addressed: id(msg) = "m" + sha256(payload bytes)[:12].  Anyone
holding a payload can compute its id, so reply-to needs no registry: the reader
unbinds the `re` slot and cleans it up against the ids of payloads it has seen.
`re` / `thread` fillers are atom("msg:"+id) passed as embedded vectors, so ids
never enter shared/vocab.txt.

Decoding from the payload alone (decode()):
  1. shape/dtype check, bit balance (a hypervector is ~50% ones) -> "malformed"
  2. language.read_back finds no structure  -> "foreign" (random bits and a
     language with other atoms look the same: honest "not ours")
  3. check==proto_v1 but act/from unreadable -> "garbled"; no marker -> "bare"
     (a meaning in the language, but not a protocol message)
  4. RE-ENCODING AGREEMENT: re-encode what was read (with the recovered ids) and
     compare to the received vector.  A perfect read of an intact payload gives
     1.0; a payload with bit-flip rate p gives 1-2p, so flip_est = (1-agree)/2.
     flip_est <= 0.05 -> "ok", else "noisy" (meaning read, but the payload is
     damaged: treat its content with flip_est-scaled caution).

A CONVERSATION is a representation too (Thread):
  * thread.vector()  = encode([msg_0, msg_1, ...]) : one vector for the whole
                       exchange; turn(i) recovers message i by cleanup.
  * thread.distill() = what the conversation ESTABLISHED, as meanings:
                       ask(s r ?) + answer(obj x) -> fact (s r x) with src=answerer;
                       assert/propose + agree -> fact endorsed by the agreer;
                       disagree -> disputed.  This is what feeds memory's KB.
  * profiles/route   = per-agent bundle of what each agent has said; route a new
                       question to the agent whose profile it matches best.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(HERE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import language as L  # noqa: E402  (lexicon's shared language)

PROTO = "proto_v1"
AGENTS = ["lexicon", "courier", "memory", "reasoner", "orchestrator", "all"]
SPEECH_ACTS = ["assert", "tell", "ask", "answer", "propose", "agree", "disagree",
               "ack", "grade", "define", "done", "query"]
CONFS = ["conf_hi", "conf_mid", "conf_lo"]
ENVELOPE = ("act", "from", "to", "check", "conf", "re", "thread", "content")
OK_FLIP = 0.05          # estimated flip rate above this -> "noisy" (meaning read, payload damaged)
BALANCE_TOL = 0.05      # |fraction of ones - 0.5| above this is not a hypervector
ID_TAU = 6.0 / np.sqrt(L.D)


# ---------------------------------------------------------------- ids
def msg_id(payload: np.ndarray) -> str:
    return "m" + hashlib.sha256(np.ascontiguousarray(payload).tobytes()).hexdigest()[:12]


def id_vec(mid: str) -> np.ndarray:
    return L.atom("msg:" + mid)


# ---------------------------------------------------------------- message
@dataclass
class Message:
    act: Optional[str]
    sender: Optional[str]
    to: Optional[str]
    content: Any
    re: Optional[str] = None           # parent message id
    thread: Optional[str] = None       # root message id
    conf: Optional[str] = None
    id: Optional[str] = None
    status: str = "ok"                 # ok | noisy | garbled | bare | foreign | malformed
    agree: float = 1.0                 # re-encoding agreement (1.0 = perfect)
    flip_est: float = 0.0              # estimated bit-flip rate of the payload
    scores: Dict[str, float] = field(default_factory=dict)
    re_score: float = 0.0
    vector: Optional[np.ndarray] = None

    def meaning(self, ids_as_vectors: bool = True) -> Dict[str, Any]:
        m: Dict[str, Any] = {"act": self.act, "from": self.sender, "check": PROTO}
        if self.to:
            m["to"] = self.to
        if self.conf:
            m["conf"] = self.conf
        if self.re:
            m["re"] = id_vec(self.re) if ids_as_vectors else self.re
        if self.thread:
            m["thread"] = id_vec(self.thread) if ids_as_vectors else self.thread
        if self.content is not None:
            m["content"] = self.content
        return m

    def text(self) -> str:
        """Human surface: the language's s-expression, ids shown as ^id."""
        m = self.meaning(ids_as_vectors=False)
        for k in ("re", "thread"):
            if k in m:
                m[k] = "^" + m[k]
        return L.show(m)

    @property
    def root(self) -> Optional[str]:
        return self.thread or self.id


def compose(sender: str, to: str, act: str, content: Any, re: Optional[str] = None,
            thread: Optional[str] = None, conf: Optional[str] = None,
            lex: Optional[L.Lexicon] = None) -> Message:
    """Build a message and its vector.  New content words are registered in
    shared/vocab.txt (by language.encode) so every reader can decode them."""
    if isinstance(content, str) and content.lstrip()[:1] in "([":
        content = L.parse(content)
    msg = Message(act, sender, to, content, re=re, thread=thread, conf=conf)
    msg.vector = L.encode(msg.meaning(), lex)
    msg.id = msg_id(L.to_wire(msg.vector))
    return msg


def wire(msg: Message) -> np.ndarray:
    return L.to_wire(msg.vector)


# ---------------------------------------------------------------- decoding
def _clean_id(u: np.ndarray, known: Sequence[str]):
    if not known:
        return None, 0.0
    M = np.stack([id_vec(k) for k in known]).astype(np.float32)
    s = M @ u.astype(np.float32) / L.D
    i = int(np.argmax(s))
    return (known[i], float(s[i])) if s[i] >= ID_TAU else (None, float(s[i]))


def decode(payload, known_ids: Sequence[str] = (), lex: Optional[L.Lexicon] = None) -> Message:
    """Payload alone -> Message with a status (see module doc)."""
    lex = lex or L.default_lexicon()
    bad = Message(None, None, None, None, status="malformed", agree=0.0, flip_est=0.5)
    if payload is None:
        return bad
    p = np.asarray(payload)
    if p.dtype != np.uint8 or p.size * 8 != lex.dim:
        return bad
    mid = msg_id(p)
    v = L.from_wire(p, lex.dim)
    ones = float((v > 0).mean())
    if abs(ones - 0.5) > BALANCE_TOL:
        bad.id = mid
        return bad
    r = L.read_back(v, lex)
    if r.kind == "noise" or r.meaning is None:
        return Message(None, None, None, None, id=mid, status="foreign", agree=0.0,
                       flip_est=0.5, vector=v)
    m = r.meaning if isinstance(r.meaning, dict) else {"content": r.meaning}
    re, re_s = _clean_id(L.unbind_role(v, "re"), known_ids)
    th, _ = _clean_id(L.unbind_role(v, "thread"), known_ids)
    msg = Message(m.get("act"), m.get("from"), m.get("to"), m.get("content"),
                  re=re, thread=th, conf=m.get("conf"), id=mid, scores=r.scores,
                  re_score=re_s, vector=v)
    is_msg = m.get("check") == PROTO and msg.act is not None and msg.sender is not None
    # re-encoding agreement: what we read, written again, vs what arrived
    if is_msg:
        again = L._enc(msg.meaning(), lex.dim)
    else:
        again = L._enc(r.meaning, lex.dim)
    msg.agree = float(np.mean(again == v) * 2 - 1)
    msg.flip_est = (1 - msg.agree) / 2
    if not is_msg:
        msg.status = "garbled" if m.get("check") == PROTO else "bare"
        if msg.status == "bare":
            msg.content = r.meaning
    else:
        msg.status = "ok" if msg.flip_est <= OK_FLIP else "noisy"
    return msg


def noisy(payload: np.ndarray, p: float, rng=None) -> np.ndarray:
    """Flip a fraction p of the payload's bits (for tests / channel noise demos)."""
    rng = rng or np.random.default_rng()
    bits = np.unpackbits(np.asarray(payload, dtype=np.uint8))
    flip = rng.random(bits.size) < p
    return np.packbits(bits ^ flip.astype(np.uint8))


# ---------------------------------------------------------------- channel glue
def send(sender: str, to: str, act: str, content: Any, re: Optional[str] = None,
         thread: Optional[str] = None, conf: Optional[str] = None,
         lex: Optional[L.Lexicon] = None) -> Message:
    """Compose and post on channel.py.  If `re` is given and `thread` is not,
    the thread is inherited from the parent (looked up on the channel)."""
    import channel
    if re and not thread:
        par = {x.id: x for x in inbox()}.get(re)
        thread = (par.root if par else re)
    msg = compose(sender, to, act, content, re=re, thread=thread, conf=conf, lex=lex)
    channel.post(sender, to, msg.text(), payload=wire(msg), kind=act,
                 proto=PROTO, id=msg.id)
    return msg


def _same_text(m: Message, text: str) -> bool:
    """Frames are unordered: compare the parsed text with the decoded meaning."""
    try:
        return L.canonical(L.parse(text)) == L.canonical(L.parse(m.text()))
    except Exception:
        return False


def inbox(me: Optional[str] = None, since: float = 0.0,
          lex: Optional[L.Lexicon] = None) -> List[Message]:
    """Every channel message with a payload, decoded FROM THE PAYLOAD ONLY (the
    text field is not used).  Ids of earlier payloads are the candidates for
    re/thread.  `me` filters to messages addressed to me or all."""
    import channel
    lex = lex or L.default_lexicon()
    lex.reload()
    known: List[str] = []
    out: List[Message] = []
    for raw in channel.read(since=0.0):
        pl = raw.get("payload")
        if pl is None:
            continue
        mid = msg_id(pl)
        m = decode(pl, known_ids=known, lex=lex)
        known.append(mid)
        m.ts, m.raw_from, m.raw_to, m.raw_text = raw["ts"], raw["from"], raw["to"], raw["text"]
        # does the human text say what the payload says?  (spoofing / drift check)
        m.text_matches = m.status in ("ok", "noisy") and _same_text(m, raw["text"])
        # does the channel's sender field agree with the sender INSIDE the payload?
        m.from_matches = (m.sender is None or m.sender == raw["from"])
        if raw["ts"] <= since:
            continue
        if me and (m.to or raw["to"]) not in (me, "all"):
            continue
        out.append(m)
    return out


# ---------------------------------------------------------------- conversations
def _fill(q: Any, answer: Any) -> Any:
    """Put the answer into the '?' slot of a question meaning."""
    if q == "?":
        return answer
    if isinstance(q, dict):
        return {k: _fill(v, answer) for k, v in q.items()}
    if isinstance(q, list):
        return [_fill(v, answer) for v in q]
    return q


def _answer_value(content: Any) -> Any:
    """An answer's content is either the filled fact or {obj: x}/an atom."""
    if isinstance(content, dict) and set(content) - {"act", "conf"} == {"obj"}:
        return content["obj"]
    return content


def _has_q(m: Any) -> bool:
    if m == "?":
        return True
    if isinstance(m, dict):
        return any(_has_q(v) for v in m.values())
    if isinstance(m, list):
        return any(_has_q(v) for v in m)
    return False


META = ("act", "conf", "because", "rule", "agent", "src")   # not part of the established triple


class Thread:
    def __init__(self, messages: Sequence[Message]):
        self.messages = list(messages)

    @classmethod
    def all(cls, msgs: Sequence[Message]) -> Dict[str, "Thread"]:
        by: Dict[str, List[Message]] = {}
        for m in msgs:
            if m.status == "ok":
                by.setdefault(m.root, []).append(m)
        return {k: cls(v) for k, v in by.items()}

    def vector(self) -> np.ndarray:
        """The whole conversation as one vector: a list of embedded message vectors."""
        return L.encode([m.vector for m in self.messages[:L.MAX_POS]], persist=False)

    def turn(self, tv: np.ndarray, i: int):
        """Recover which known message sits at turn i of a thread vector."""
        u = L.unbind_role(tv, f"#{i}")
        sims = [L.sim(u, m.vector) for m in self.messages]
        j = int(np.argmax(sims))
        return self.messages[j], float(sims[j])

    def distill(self) -> List[Dict[str, Any]]:
        """What this conversation established, as meanings with provenance."""
        by_id = {m.id: m for m in self.messages}
        out: List[Dict[str, Any]] = []
        for m in self.messages:
            par = by_id.get(m.re) if m.re else None
            if m.act == "answer" and par is not None and par.act in ("ask", "query") \
                    and _has_q(par.content):
                val = _answer_value(m.content)
                if val in (None, "unknown", "?") or (
                        isinstance(val, dict) and (val.get("obj") in ("unknown", "?") or _has_q(val))):
                    continue                     # abstention / unanswered: nothing established
                fact = _fill(par.content, val) if not isinstance(val, dict) else val
                if isinstance(fact, dict):
                    fact = {k: v for k, v in fact.items() if k not in META}
                # an answer listing several values establishes one fact per value
                facts = ([{**fact, "obj": o} for o in fact["obj"]]
                         if isinstance(fact, dict) and isinstance(fact.get("obj"), list) else [fact])
                for fa in facts:
                    out.append({"fact": fa, "src": m.sender, "asked_by": par.sender,
                                "via": m.id, "endorsed": [], "disputed": []})
            elif m.act in ("assert", "tell", "propose") and isinstance(m.content, dict):
                fact = {k: v for k, v in m.content.items() if k not in META}
                out.append({"fact": fact, "src": m.sender, "asked_by": None,
                            "via": m.id, "endorsed": [], "disputed": [],
                            "proposal": m.act == "propose"})
        seen, uniq = set(), []
        for f in out:                       # same fact from the same source once
            k = (L.show(f["fact"]), f["src"])
            if k not in seen:
                seen.add(k); uniq.append(f)
        out = uniq
        idx = {f["via"]: f for f in out}
        for m in self.messages:
            f = idx.get(m.re) if m.re else None
            if f is None:
                continue
            if m.act == "agree" and m.sender != f["src"]:
                f["endorsed"].append(m.sender)
            elif m.act == "disagree" and m.sender != f["src"]:
                f["disputed"].append(m.sender)
        return out


def lift(m: Message) -> Optional[Message]:
    """A 'bare' meaning with a speech act at its head (e.g. lexicon's
    (propose :subj .. :agent lexicon :because ..)) read as a message: act = its
    head, sender = its :agent (else the channel sender, marked unverified),
    content = the rest.  Lets bare proposals be agreed to and distilled."""
    if m.status != "bare" or not isinstance(m.content, dict):
        return None
    c = dict(m.content)
    act = c.pop("act", None)
    if act not in SPEECH_ACTS:
        return None
    who = c.pop("agent", None) or getattr(m, "raw_from", None)
    c.pop("because", None)
    out = Message(act, who, c.pop("to", None), c, id=m.id, status="ok", agree=m.agree,
                  flip_est=m.flip_est, scores=m.scores, vector=m.vector)
    out.lifted = True
    return out


def distill_all(msgs: Sequence[Message]) -> List[Dict[str, Any]]:
    """Distill over all messages (reply chains may cross thread roots);
    bare act-headed meanings are lifted into messages first."""
    use = []
    for m in msgs:
        if m.status in ("ok", "noisy"):
            use.append(m)
        elif m.status == "bare":
            lm = lift(m)
            if lm is not None:
                use.append(lm)
    return Thread(use).distill()


def to_kb(facts: Iterable[Dict[str, Any]], kb, via: str = "courier") -> Dict[str, int]:
    """Feed distilled facts into memory's KB: the teller tells, each endorser
    grades ok, each disputer grades bad (self-grades are skipped)."""
    n = {"told": 0, "graded": 0, "skipped": 0}
    for f in facts:
        fa = f["fact"]
        s, r, o = fa.get("subj"), fa.get("rel"), fa.get("obj")
        if not all(isinstance(x, str) for x in (s, r, o)):
            n["skipped"] += 1
            continue
        try:
            fid = kb.tell(f["src"], s, r, o, via=via)
        except TypeError:                   # a KB without relay support
            fid = kb.tell(f["src"], s, r, o)
        n["told"] += 1
        for who, ok in [(a, True) for a in f["endorsed"]] + [(a, False) for a in f["disputed"]]:
            if who == f["src"]:
                continue
            kb.grade(who, fid, ok, how="confirmed")
            n["graded"] += 1
    return n


# ---------------------------------------------------------------- routing
def _content_vec(m: Message) -> Optional[np.ndarray]:
    if m.content is None:
        return None
    return L.encode(m.content, persist=False)


def profiles(msgs: Sequence[Message], acts=("assert", "tell", "answer", "propose", "define")
             ) -> Dict[str, np.ndarray]:
    """Per-agent SUM (int32, unsigned: no capacity lost to the sign) of the content
    vectors that agent has asserted/answered: 'what this agent talks about'."""
    acc: Dict[str, np.ndarray] = {}
    for m in msgs:
        if m.status not in ("ok", "noisy") or m.act not in acts or m.sender in (None, "all"):
            continue
        cv = _content_vec(m)
        if cv is not None:
            acc[m.sender] = acc.get(m.sender, 0) + cv.astype(np.int32)
    return acc


def _leaves(m: Any, path=()):
    """(role path, atom) for every known leaf of a meaning, skipping ?, act, markers."""
    if isinstance(m, str):
        if m not in ("?", "unknown") and path and path[-1] != "act":
            yield path, m
    elif isinstance(m, dict):
        for k, v in m.items():
            yield from _leaves(v, path + (str(k).lower(),))
    elif isinstance(m, (list, tuple)):
        for i, v in enumerate(m):
            yield from _leaves(v, path + (f"#{i}",))


def route(content: Any, profs: Dict[str, np.ndarray], exclude: Sequence[str] = ()):
    """Who has talked about this?  The question is asked OF each profile in the
    language: for every known leaf (role path, word) of the content, unbind the
    role path from the profile and measure how strongly the word is there.
    Returns [(agent, score), ...] best first (score = mean z over the leaves)."""
    if isinstance(content, str) and content.lstrip()[:1] in "([":
        content = L.parse(content)
    leaves = list(_leaves(content))
    agents = [a for a in profs if a not in exclude]
    Z = np.zeros((len(agents), len(leaves)), np.float32)
    for i, a in enumerate(agents):
        pv = np.asarray(profs[a], dtype=np.float32)
        for j, (path, w) in enumerate(leaves):
            u = pv
            for r in path:
                u = np.roll(u * L.role(r).astype(np.float32), -1)
            Z[i, j] = float(u @ L.atom(w).astype(np.float32)) / (np.linalg.norm(pv) + 1e-9)
    # score = mean z over the query's leaves (z in noise units: an absent word
    # is ~N(0,1), a word the agent said once is ~4-8).
    ranked = [(a, float(Z[i].mean()) if leaves else 0.0) for i, a in enumerate(agents)]
    return sorted(ranked, key=lambda t: -t[1])


# ---------------------------------------------------------------- reproducible checks (memory's KB)
def check(kb, check_str: str) -> Optional[bool]:
    """Re-run a protocol claim.  Registered with knowledge.py as prefix 'proto':
        proto:roundtrip:<s-expr>            the content survives compose -> wire -> decode
        proto:noise:<p>:<n>:<min_exact>     >= min_exact of n random messages decode exactly at flip rate p
        proto:flipest:<p>:<n>:<max_err>     mean |flip_est - p| <= max_err at flip rate p
        proto:foreign:<n>                   0 of n random payloads decode as messages
        proto:reply:<child_id>:<parent_id>  on the channel, the child's payload replies to the parent
    Private Lexicon(path=None) + fixed seeds: nothing is written to vocab.txt."""
    try:
        _, kind, rest = check_str.split(":", 2)
        lex = L.Lexicon(path=None)
        rng = np.random.default_rng(12345)
        words = [f"w{i}" for i in range(200)]
        lex.learn(words, persist=False)

        def rnd(parent=None):
            s, o = rng.choice(words, 2, replace=False)
            return compose("memory", "reasoner", "assert",
                           {"act": "fact", "subj": str(s), "rel": "r", "obj": str(o)},
                           re=parent, lex=lex)

        if kind == "roundtrip":
            m = compose("courier", "all", "tell", L.parse(rest), lex=lex)
            d = decode(wire(m), lex=lex)
            return d.status == "ok" and L.canonical(d.content) == L.canonical(m.content)
        if kind in ("noise", "flipest"):
            p, n, lim = rest.split(":")
            p, n, lim = float(p), int(n), float(lim)
            ids = [f"m{i:012x}" for i in range(50)]
            ex, err = 0, []
            for i in range(n):
                m = rnd(parent=ids[i % 50])
                d = decode(noisy(wire(m), p, rng), known_ids=ids, lex=lex)
                ex += (d.content is not None and d.re == m.re
                       and L.canonical(d.content) == L.canonical(m.content))
                err.append(abs(d.flip_est - p))
            return ex / n >= lim if kind == "noise" else float(np.mean(err)) <= lim
        if kind == "foreign":
            n = int(rest)
            return all(decode(rng.integers(0, 256, L.D // 8).astype(np.uint8), lex=lex).status
                       not in ("ok", "noisy") for _ in range(n))
        if kind == "reply":
            child, parent = rest.split(":")
            got = {m.id: m for m in inbox()}
            return child in got and got[child].re == parent
    except Exception:
        return None
    return None


try:
    import knowledge as _K
    _K.register_checker("proto", check)
except Exception:          # knowledge.py absent or broken: protocol still works
    pass


# ---------------------------------------------------------------- serving questions
def pending(me: str, msgs: Optional[Sequence[Message]] = None) -> List[Message]:
    """Questions (ask/query, readable, containing '?') addressed to me or all
    that I have not answered yet (no answer/ack from me with re = its id)."""
    msgs = inbox() if msgs is None else msgs
    done = {m.re for m in msgs if m.sender == me and m.act in ("answer", "ack", "disagree") and m.re}
    return [m for m in msgs if m.status in ("ok", "noisy") and m.act in ("ask", "query")
            and m.sender != me and (m.to in (me, "all")) and m.id not in done
            and _has_q(m.content)]


def serve(me: str, handler, msgs: Optional[Sequence[Message]] = None) -> List[Message]:
    """Answer every pending question with handler(content) -> answer content
    (a meaning; 'unknown' to abstain; None to skip).  Answers reply to the
    question, so distill() can turn each Q/A pair into a fact."""
    sent = []
    for q in pending(me, msgs):
        a = handler(q.content)
        if a is None:
            continue
        sent.append(send(me, q.sender, "answer", a, re=q.id, thread=q.root))
    return sent


def kb_handler(kb):
    """A handler that answers (query :subj s :rel r :obj ?) from memory's KB,
    with conf from the KB's trust; abstains with 'unknown' when uncertain."""
    def h(content):
        if not isinstance(content, dict):
            return None
        s, r = content.get("subj"), content.get("rel")
        if content.get("obj") != "?" or not isinstance(s, str) or not isinstance(r, str):
            return None
        ans = kb.ask(s, r)
        if getattr(ans, "status", None) != "answered" or ans.obj is None:
            return {"act": "fact", "subj": s, "rel": r, "obj": "unknown"}
        return {"act": "fact", "subj": s, "rel": r, "obj": ans.obj}
    return h


# ---------------------------------------------------------------- long contents (over the leaf budget)
ENVELOPE_LEAVES = 12    # envelope overhead incl. re/thread/seq, with margin


def split(items: Sequence[Any], dim: int = L.D) -> List[List[Any]]:
    """Greedy chunks of a list so that each chunk + envelope fits the leaf budget."""
    budget = L.max_leaves(dim) - ENVELOPE_LEAVES
    chunks: List[List[Any]] = [[]]
    used = 1
    for it in items:
        n = L.leaf_count(it)
        if chunks[-1] and (used + n > budget or len(chunks[-1]) >= L.MAX_POS):
            chunks.append([]); used = 1
        chunks[-1].append(it); used += n
    return chunks


def compose_parts(sender: str, to: str, act: str, items: Sequence[Any],
                  lex: Optional[L.Lexicon] = None) -> List[Message]:
    """A list too long for one vector, as a chain of messages: part k carries
    :seq p<k>of<n>, :thread = part 1's id and :re = the previous part, so the
    receiver can check order and completeness from the payloads alone."""
    chunks = split(items, (lex or L.default_lexicon()).dim)
    n = len(chunks)
    out: List[Message] = []
    for k, ch in enumerate(chunks, 1):
        prev = out[-1].id if out else None
        root = out[0].id if out else None
        m = Message(act, sender, to, ch, re=prev, thread=root)
        mm = m.meaning()
        mm["seq"] = f"p{k}of{n}"
        m.vector = L.encode(mm, lex)
        m.id = msg_id(L.to_wire(m.vector))
        m.seq = mm["seq"]
        out.append(m)
    return out


def _seq_of(m: Message, lex: Optional[L.Lexicon] = None):
    lex = lex or L.default_lexicon()
    w, s = lex.cleanup(L.unbind_role(m.vector, "seq"))
    if s < lex.threshold() or not (w.startswith("p") and "of" in w):
        return None
    try:
        k, n = w[1:].split("of")
        return int(k), int(n)
    except ValueError:
        return None


def reassemble(msgs: Sequence[Message], root: str,
               lex: Optional[L.Lexicon] = None) -> Optional[List[Any]]:
    """Join the parts of a multi-part message (decoded payloads).  Returns None
    unless every part 1..n is present, each part's re is the previous part and
    each list decoded completely."""
    parts = {}
    for m in msgs:
        if m.status not in ("ok", "noisy") or (m.id != root and m.thread != root):
            continue
        kn = _seq_of(m, lex)
        if kn:
            parts[kn[0]] = (kn[1], m)
    if not parts:
        return None
    n = next(iter(parts.values()))[0]
    if sorted(parts) != list(range(1, n + 1)):
        return None
    out: List[Any] = []
    prev = None
    for k in range(1, n + 1):
        m = parts[k][1]
        if (k > 1 and m.re != prev) or not isinstance(m.content, list):
            return None
        out.extend(m.content); prev = m.id
    return out
