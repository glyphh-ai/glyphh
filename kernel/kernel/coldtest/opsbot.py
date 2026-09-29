"""opsbot — cold-test application of the glyphh kernel.

Domain: automated incident remediation. Every decision flows through the
kernel's grounded loop exactly as KERNEL.md prescribes:

    wins Space + vetoes Space -> confidence gate -> veto check -> fallback
    -> world grades -> record into wins or vetoes.

The world is a deterministic simulator: each (service, symptom) pair has
one correct remediation action. The fallback consultant is a noisy
oracle (80% correct). At step 200 the world DRIFTS: one mapping changes,
so a previously-winning reflex starts failing — this exercises the veto
path. Novelty probes exercise the confidence gate.
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glyphh_kernel import Space, symbol

HERE = os.path.dirname(os.path.abspath(__file__))
WINS_DB = os.path.join(HERE, "wins.db")
VETOES_DB = os.path.join(HERE, "vetoes.db")

# fresh run every time
for p in (WINS_DB, VETOES_DB):
    if os.path.exists(p):
        os.remove(p)

rng = random.Random(7)

# ── the world ───────────────────────────────────────────────────────
SERVICES = ["auth", "payments", "search", "cdn"]
SYMPTOMS = ["latency", "errors", "oom", "disk_full"]
REGIONS = ["us-east", "eu-west"]
LOADS = ["normal", "peak"]
ACTIONS = ["restart", "failover", "scale_up", "rollback", "throttle"]

TRUTH = {}
_act = rng.sample(ACTIONS * 4, len(SERVICES) * len(SYMPTOMS))
i = 0
for s in SERVICES:
    for y in SYMPTOMS:
        TRUTH[(s, y)] = _act[i]
        i += 1

DRIFT_STEP = 200
DRIFT_KEY = ("payments", "latency")


def world_truth(service, symptom, step):
    if step >= DRIFT_STEP and (service, symptom) == DRIFT_KEY:
        # the world changed: old remedy no longer works
        old = TRUTH[DRIFT_KEY]
        return next(a for a in ACTIONS if a != old)
    return TRUTH[(service, symptom)]


def world_grades(action, service, symptom, step):
    """The world, not a human: deterministic grading."""
    return action == world_truth(service, symptom, step)


def make_incident(step):
    # force the drifting pair to appear regularly so both phases see it
    if step % 10 == 3:
        service, symptom = DRIFT_KEY
    else:
        service, symptom = rng.choice(SERVICES), rng.choice(SYMPTOMS)
    situation = {
        "service": service,
        "symptom": symptom,
        "region": rng.choice(REGIONS),
        "load": rng.choice(LOADS),
    }
    events = [symbol(f"evt:{symptom}:onset"),
              symbol(f"evt:load:{situation['load']}")]
    return situation, events


def oracle(situation, events, step):
    """Noisy fallback consultant: 80% correct, else random wrong."""
    correct = world_truth(situation["service"], situation["symptom"], step)
    if rng.random() < 0.80:
        return correct
    return rng.choice([a for a in ACTIONS if a != correct])


# ── the grounded loop, verbatim from KERNEL.md ─────────────────────
wins, vetoes = Space(path=WINS_DB), Space(path=VETOES_DB)


def decide(situation, events, fallback):
    a = wins.query(situation, events)
    if a.sufficient and a.confidence >= 0.5:
        v = vetoes.query(situation, events)
        if not (v.sufficient and v.top == a.top and v.confidence >= 0.5):
            return a.top, "reflex"
    return fallback(situation, events), "consult"


# ── run ─────────────────────────────────────────────────────────────
N_STEPS = 400
log = []
veto_demo = []

for step in range(N_STEPS):
    situation, events = make_incident(step)
    fb = lambda s, e: oracle(s, e, step)
    action, mode = decide(situation, events, fb)
    success = world_grades(action, situation["service"],
                           situation["symptom"], step)
    (wins if success else vetoes).record(situation, action, events)
    log.append({"step": step, "situation": situation, "action": action,
                "mode": mode, "success": success,
                "drift_pair": (situation["service"],
                               situation["symptom"]) == DRIFT_KEY})
    # trace the drifting pair around the drift for the veto demo
    if log[-1]["drift_pair"] and DRIFT_STEP - 30 <= step < DRIFT_STEP + 60:
        veto_demo.append(log[-1])

# ── metrics ─────────────────────────────────────────────────────────
def rate(rows, key):
    return sum(1 for r in rows if r[key]) / len(rows) if rows else float("nan")

quartiles = [log[i * N_STEPS // 4:(i + 1) * N_STEPS // 4] for i in range(4)]
print("== per-quartile ==")
for qi, q in enumerate(quartiles):
    consults = [r for r in q if r["mode"] == "consult"]
    print(f"Q{qi+1} steps {q[0]['step']}-{q[-1]['step']}: "
          f"consult_rate={rate(q, 'success')*0+len(consults)/len(q):.3f} "
          f"success_rate={rate(q, 'success'):.3f}")

reflex = [r for r in log if r["mode"] == "reflex"]
consult = [r for r in log if r["mode"] == "consult"]
print(f"\noverall: n={len(log)} consult_rate={len(consult)/len(log):.3f} "
      f"success_rate={rate(log, 'success'):.3f}")
print(f"reflex:  n={len(reflex)} accuracy={rate(reflex, 'success'):.3f}")
print(f"consult: n={len(consult)} accuracy={rate(consult, 'success'):.3f}")
print(f"wins space rows={len(wins)}  vetoes space rows={len(vetoes)}")

# ── demo A: confidence gate on genuinely novel situations ───────────
print("\n== demo A: novelty probes ==")
novel_full = {"service": "quantumdb", "symptom": "bitflip",
              "region": "mars-1", "load": "singularity"}
a1 = wins.query(novel_full, [symbol("evt:bitflip:onset")])
print("fully novel situation ->", json.dumps(
    {"sufficient": a1.sufficient, "confidence": round(a1.confidence, 3),
     "support": round(a1.support, 3), "top": a1.top}))

novel_partial = {"service": "quantumdb", "symptom": "bitflip",
                 "region": "us-east", "load": "peak"}
a2 = wins.query(novel_partial, [symbol("evt:bitflip:onset"),
                                symbol("evt:load:peak")])
print("partially novel (familiar region/load) ->", json.dumps(
    {"sufficient": a2.sufficient, "confidence": round(a2.confidence, 3),
     "support": round(a2.support, 3), "top": a2.top}))

# ── demo B: veto prevents a discredited reflex from repeating ───────
print("\n== demo B: drift pair trace (payments/latency, drift at step "
      f"{DRIFT_STEP}; old truth={TRUTH[DRIFT_KEY]}, "
      f"new truth={world_truth(*DRIFT_KEY, DRIFT_STEP)}) ==")
for r in veto_demo:
    print(f"step {r['step']:3d} mode={r['mode']:7s} action={r['action']:9s} "
          f"success={r['success']}")

# count: after first post-drift failure, did the discredited action fire
# again as a reflex on the drift pair?
post = [r for r in log if r["drift_pair"] and r["step"] >= DRIFT_STEP]
first_fail = next((i for i, r in enumerate(post) if not r["success"]), None)
repeats = [r for r in post[first_fail + 1:]
           if r["mode"] == "reflex" and r["action"] == TRUTH[DRIFT_KEY]] \
    if first_fail is not None else []
print(f"\npost-drift encounters of drift pair: {len(post)}; "
      f"discredited reflex repeats after first failure: {len(repeats)}")

with open(os.path.join(HERE, "run_log.json"), "w") as f:
    json.dump(log, f, indent=1)
print("\nlog written to run_log.json")
