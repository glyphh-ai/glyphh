"""The reasoner's turn on the shared KB: derive, tell, grade, answer.

    python3 reasoner/agent.py [--dry] [--no-grade] [--no-channel]

One turn:
  1. read the group's KB (memory's shared/knowledge.py), as facts
  2. INFER new claims from them (shared/reason.py):
       closure       transitive relations (is_a, part_of, contains, ...)
       ordinal       unmeasured points of a measured family f(param)
     each told with evidence = premise claim ids and a confidence, and
     its conclusion glyph conclude(claim, premises, rule) posted
  3. GRADE other agents' claims I can reproduce:
       measurements  re-measure in my own world draw (memory/world.py)
       derived       re-derive from the cited premises
  4. ANSWER questions addressed to me/all on the channel, in glyphs
"""

from __future__ import annotations

import json
import os
import sys
import zlib
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, ".."))
for p in (AGENTS, os.path.join(AGENTS, "shared"), os.path.join(AGENTS, "memory")):
    if p not in sys.path:
        sys.path.insert(0, p)

import reason as rz  # noqa: E402
from reason import Frames, closure, conclude, fact_glyph, ordinal_infer  # noqa: E402

ME = "reasoner"
TRANSITIVE = ("is_a", "part_of", "contains", "depends_on", "implies")
STATE = os.path.join(HERE, "state.json")
# premises must be graded by someone other than their author: a
# claimed-only premise (0.5) cannot carry a conclusion over the 0.5 bar
STATUS_CONF = {"known": 1.0, "uncertain": 0.9, "claimed": 0.5}


def _load_state() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"read_ts": 0.0}


def _save_state(s: dict) -> None:
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


_PEER_CLAIMS: Dict[str, object] = {}


def _peer_claims(agent: str, name: str = "claims"):
    """<agent>/<name>.py: another agent's measurements, each reproducible
    with my own seed. Loaded by path so module names cannot clash."""
    key = f"{agent}/{name}"
    if key not in _PEER_CLAIMS:
        mod = None
        path = os.path.join(AGENTS, agent, name + ".py")
        if os.path.exists(path):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"{agent}_{name}", path)
                mod = importlib.util.module_from_spec(spec)
                if os.path.dirname(path) not in sys.path:
                    sys.path.append(os.path.dirname(path))
                spec.loader.exec_module(mod)
            except Exception:
                mod = None
        _PEER_CLAIMS[key] = mod
    return _PEER_CLAIMS[key]


def _lexicon_claims():
    return _peer_claims("lexicon")


PEERS = ("lexicon", "memory", "courier")


def _ctx_key(ctx: Dict[str, str]) -> str:
    return json.dumps(ctx, sort_keys=True)


def _num(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class Reasoner:
    def __init__(self, kb=None, dry: bool = False, post=None):
        if kb is None:
            from knowledge import KB
            kb = KB()
        self.kb = kb
        self.dry = dry
        self.post = post            # callable(text, glyph) or None
        self.log: List[str] = []

    # ── 1. the KB as facts ───────────────────────────────────────────
    def beliefs(self) -> List[Tuple[object, object]]:
        """[(claim, belief)] for every claim whose question is not vetoed
        or contested; the belief is the group's current answer."""
        self.kb.refresh()
        out, seen = [], {}
        for c in self.kb.all_claims():
            key = (c.subject, c.relation, _ctx_key(c.context))
            if key not in seen:
                seen[key] = self.kb.ask_situation(c.situation, asker=ME, log=False)
            b = seen[key]
            if b.status in ("vetoed", "contested"):
                continue
            if b.value is not None and b.value != c.value:
                continue            # the group believes something else
            out.append((c, b))
        return out

    def _already(self, subject, relation, value, context=None) -> bool:
        ctx = _ctx_key(context or {})
        return any(c.subject == subject and c.relation == relation and
                   c.value == value and _ctx_key(c.context) == ctx
                   for c in self.kb.all_claims())

    def _tell(self, s, r, o, context, evidence, conf, how, premise_glyphs, rule):
        if self._already(s, r, o, context):
            return None
        cid = None
        if not self.dry:
            cid = self.kb.tell(ME, s, r, o, context=context or None,
                               evidence=evidence, confidence=round(conf, 4),
                               how=how)
        g = conclude(fact_glyph(s, r, o), premise_glyphs, rule, conf)
        self.log.append(f"told {cid}: {s} {r} {o} {context or ''} "
                        f"conf={conf:.2f} rule={rule} ev={evidence}")
        return cid, g

    # ── 2a. transitive closure ───────────────────────────────────────
    def infer_closure(self) -> List[tuple]:
        facts, cid_of, pconf = [], {}, {}
        for c, b in self.beliefs():
            if c.relation in TRANSITIVE and not c.context:
                f = (c.subject, c.relation, c.value)
                facts.append(f)
                cid_of.setdefault(f, c.id)
                pconf[f] = max(pconf.get(f, 0.0), STATUS_CONF.get(b.status, 0.0))
        kb = Frames(facts)
        made = []
        for rel in TRANSITIVE:
            if not any(f[1] == rel for f in facts):
                continue
            for d in closure(kb, rel):
                conf = d.conf * min(pconf.get(p, 0.0) for p in d.premises)
                if conf < 0.5:
                    continue        # rests on a premise nobody reproduced
                ev = [cid_of[p] for p in d.premises if p in cid_of]
                prem = [fact_glyph(*p) for p in d.premises]
                r = self._tell(*d.fact, None, ev, conf,
                               f"reason.closure({rel}) depth {d.depth}: "
                               + " , ".join(" ".join(p) for p in d.premises),
                               prem, "transitive")
                if r:
                    made.append(r)
        return made

    # ── 2b. ordinal inference over measured families ─────────────────
    def families(self):
        """(subject, relation, fixed-context, param) -> {x: (value, conf, cid)}"""
        fams: Dict[tuple, Dict[float, tuple]] = {}
        for c, b in self.beliefs():
            conf = STATUS_CONF.get(b.status)
            if conf is None:
                continue
            for k, v in c.context.items():
                x = _num(v)
                if x is None:
                    continue
                fixed = {kk: vv for kk, vv in c.context.items() if kk != k}
                key = (c.subject, c.relation, _ctx_key(fixed), k)
                prev = fams.setdefault(key, {}).get(x)
                if prev is None or conf > prev[1]:
                    fams[key][x] = (c.value, conf, c.id)
        return fams

    def grid_for(self, subject, relation, fixed, param) -> List[float]:
        """Points worth concluding about: the world's question grid for
        this family (memory/world.py questions())."""
        try:
            from world import questions
        except Exception:
            return []
        fixed = json.loads(fixed)
        xs = []
        qs = list(questions())
        for peer in PEERS:
            pm = _peer_claims(peer)
            qs += list(getattr(pm, "QUESTIONS", []) or []) if pm is not None else []
        for s, r, ctx in qs:
            if (s, r) != (subject, relation) or param not in ctx:
                continue
            if all(ctx.get(k) == v for k, v in fixed.items()):
                xs.append(float(ctx[param]))
        return sorted(set(xs))

    def rule_reliability(self, prior_weight: float = 20.0) -> Dict[str, dict]:
        """Learn how far to trust each of MY inference rules from the
        grades other agents gave the claims it produced: a Beta update
        of the bench prior (prior_weight pseudo-grades). This is the
        feedback loop: vetoes on my inferences lower my confidence in
        the rule that made them."""
        out = {}
        tally: Dict[str, List[int]] = {}
        for c in self.kb.all_claims(author=ME):
            rule = None
            if c.how.startswith("reason.ordinal_infer "):
                rule = c.how.split()[1]
            elif c.how.startswith("reason.closure("):
                rule = "transitive"
            if rule is None:
                continue
            t = tally.setdefault(rule, [0, 0])
            for g in self.kb.grades(c.id):
                t[0] += int(g["ok"])
                t[1] += 1
        for rule, prior in list(rz.ORDINAL_RULE_CONF.items()) + [("transitive", 0.99)]:
            wins, n = tally.get(rule, [0, 0])
            out[rule] = {"prior": prior, "wins": wins, "graded": n,
                         "conf": (prior * prior_weight + wins) / (prior_weight + n)}
        return out

    def infer_ordinal(self) -> List[tuple]:
        made = []
        rel = self.rule_reliability()
        rule_conf = {k: rel[k]["conf"] for k in rz.ORDINAL_RULE_CONF}
        self.log.append("rule reliability from grades: " + ", ".join(
            f"{k} {v['wins']}/{v['graded']} -> {v['conf']:.3f}" for k, v in rel.items()))
        for (s, r, fixed, param), pts in self.families().items():
            grid = self.grid_for(s, r, fixed, param)
            values = {x: v[0] for x, v in pts.items()}
            for oc in ordinal_infer(values, grid, rule_conf=rule_conf):
                prem_conf = min(pts[p][1] for p in oc.premises)
                conf = oc.conf * prem_conf
                if conf < 0.5:
                    continue
                ctx = dict(json.loads(fixed))
                ctx[param] = str(int(oc.param)) if oc.param == int(oc.param) else str(oc.param)
                ev = [pts[p][2] for p in oc.premises]
                prem = [fact_glyph(s, r, pts[p][0]) for p in oc.premises]
                res = self._tell(s, r, oc.value, ctx, ev, conf,
                                 f"reason.ordinal_infer {oc.rule} depth {oc.depth} "
                                 f"from {param}={oc.premises}", prem, oc.rule)
                if res:
                    made.append(res)
        return made

    def infer_one(self, s: str, r: str, ctx: Dict[str, str]) -> Optional[dict]:
        """Answer ONE question the KB cannot: by ordinal inference over
        its family, or by a transitive chain. None = I don't know."""
        fams = self.families()
        for k, v in ctx.items():
            x = _num(v)
            if x is None:
                continue
            fixed = _ctx_key({kk: vv for kk, vv in ctx.items() if kk != k})
            pts = fams.get((s, r, fixed, k))
            if not pts:
                continue
            rel = self.rule_reliability()
            for oc in ordinal_infer({p: q[0] for p, q in pts.items()}, [x],
                                    rule_conf={kk: rel[kk]["conf"] for kk in rz.ORDINAL_RULE_CONF}):
                conf = oc.conf * min(pts[p][1] for p in oc.premises)
                return {"value": oc.value, "conf": conf, "rule": oc.rule,
                        "evidence": [pts[p][2] for p in oc.premises]}
        if r in TRANSITIVE and not ctx:
            facts = [(c.subject, c.relation, c.value) for c, b in self.beliefs()
                     if c.relation == r and not c.context]
            for d in closure(Frames(facts), r):
                if d.fact[0] == s:
                    return {"value": d.fact[2], "conf": d.conf, "rule": "transitive",
                            "evidence": []}
        return None

    # ── 2c. lineage: inferences whose premises fell ──────────────────
    def stale(self) -> List[dict]:
        """My inferred claims resting on a premise the group no longer
        believes (vetoed, contested, or now answered differently). I
        cannot grade my own claim, so I flag it for re-grading."""
        out = []
        for c in self.kb.all_claims(author=ME):
            if not c.evidence:
                continue
            for e in c.evidence:
                try:
                    p = self.kb.claim(e)
                except KeyError:
                    continue
                b = self.kb.ask_situation(p.situation, asker=ME, log=False)
                if b.status in ("vetoed", "contested") or (
                        b.value is not None and b.value != p.value):
                    out.append({"claim": c.id, "premise": e,
                                "premise_status": b.status,
                                "group_value": b.value})
                    break
        return out

    # ── 3. grade what I can reproduce ────────────────────────────────
    def reproduce(self, c) -> Optional[str]:
        # a measurement of the language: re-measure in MY world draw
        try:
            from world import FAMILIES, measure
        except Exception:
            FAMILIES, measure = {}, None
        if measure and ((c.subject, c.relation) in FAMILIES or
                        (c.subject, c.relation) == ("situation", "overlap_sim")):
            seed = 4000 + zlib.crc32(c.id.encode()) % 100000
            try:
                return measure((c.subject, c.relation, dict(c.context)), seed)
            except (KeyError, ValueError):
                return None
        # a measurement a peer published (<author>/claims.py): re-measure
        # with MY seed; only the claim author's module is consulted
        pm = _peer_claims(c.author) if c.author in PEERS else None
        if pm is not None and hasattr(pm, "measure"):
            try:
                return str(pm.measure((c.subject, c.relation, dict(c.context)),
                                      4000 + zlib.crc32(c.id.encode()) % 100000))
            except (KeyError, ValueError):
                pass
        # codebook structure (lexicon/concepts.py): expand the definitions
        if c.relation == "part_of" and c.subject.startswith("c:"):
            cm = _peer_claims("lexicon", "concepts")
            if cm is not None:
                return cm.reproduce(c.subject, c.value)
        # a transitive derivation: re-derive from its cited premises
        if c.relation in TRANSITIVE and c.evidence:
            try:
                prem = [self.kb.claim(e) for e in c.evidence]
            except KeyError:
                return None
            kb = Frames([(p.subject, p.relation, p.value) for p in prem])
            ch = rz.chain(kb, c.subject, [c.relation] * len(prem))
            return ch.path[-1] if ch.known else None
        return None

    def grade_pending(self, limit: int = 50) -> Dict[str, int]:
        tally = {"win": 0, "veto": 0, "skip": 0}
        for c in self.kb.pending(ME, limit=limit):
            got = self.reproduce(c)
            if got is None:
                tally["skip"] += 1
                continue
            ok = got == c.value
            if not self.dry:
                self.kb.grade(ME, c.id, ok, "reasoner re-derived/re-measured"
                              if ok else f"reasoner got {got!r}")
            tally["win" if ok else "veto"] += 1
            self.log.append(f"graded {c.id} ({c.author}: {c.subject} "
                            f"{c.relation} {c.context} = {c.value}): "
                            f"{'ok' if ok else 'NO, got ' + repr(got)}")
        return tally

    # ── 4. answer questions in the language ──────────────────────────
    def answer_inbox(self, since: float) -> Tuple[int, float]:
        import protocol
        from language import Lexicon, render
        lx = Lexicon(author=ME)
        n, last = 0, since
        for line, d in protocol.inbox(ME, since=since, lx=lx):
            last = max(last, line["ts"])
            if line["from"] == ME or d.get("act") != "ask":
                continue
            q = d.content if isinstance(d.content, dict) else {}
            if not ("subject" in q and "relation" in q):
                continue
            ctx = {k: v for k, v in q.items()
                   if k not in ("subject", "relation", "object", "act", "want")
                   and isinstance(v, str)}
            b = self.kb.ask(q["subject"], q["relation"], context=ctx or None,
                            asker=ME)
            content = {"subject": q["subject"], "relation": q["relation"],
                       "object": b.value if b.value else "unknown",
                       "confidence": b.status}
            if b.status in ("unknown", "claimed"):
                inf = self.infer_one(q["subject"], q["relation"], ctx)
                if inf is not None:
                    content["object"] = inf["value"]
                    content["confidence"] = rz.conf_word(inf["conf"])
                    content["rule"] = inf["rule"]
            content.update(ctx)
            if not self.dry:
                protocol.send(ME, line["from"], "answer", content,
                              reply_ts=line["ts"], lx=lx,
                              text=f"[answer] {render(content)} "
                                   f"(count={b.count})")
            self.log.append(f"answered {line['from']}: {render(content)}")
            n += 1
        return n, last

    def turn(self, grade=True, channel=True) -> dict:
        st = _load_state()
        made = self.infer_closure() + self.infer_ordinal()
        tally = self.grade_pending() if grade else {}
        stale = self.stale()
        for x in stale:
            self.log.append(f"STALE {x['claim']}: premise {x['premise']} is "
                            f"{x['premise_status']} (group says {x['group_value']})")
        answered = 0
        if channel:
            answered, st["read_ts"] = self.answer_inbox(st.get("read_ts", 0.0))
            if not self.dry:
                _save_state(st)
        return {"told": len(made), "grades": tally, "answered": answered,
                "stale": len(stale), "made": made}


if __name__ == "__main__":
    r = Reasoner(dry="--dry" in sys.argv)
    out = r.turn(grade="--no-grade" not in sys.argv,
                 channel="--no-channel" not in sys.argv)
    for line in r.log:
        print(line)
    print({k: v for k, v in out.items() if k != "made"})
