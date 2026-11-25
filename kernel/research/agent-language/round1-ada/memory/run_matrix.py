"""Run the demo matrix: 3 veto rules x {drift, hostile grader}, 3 seeds each.
    python3 run_matrix.py > matrix_output.txt"""
import json
from demo_curve import run

for scen, kw in (("drift", dict(drift=400)),
                 ("hostile", dict(drift=10**9, hostile="courier"))):
    for rule in ("nearest", "parity", "trusted"):
        agg = []
        for seed in (7, 8, 9):
            rows, s = run(steps=800, veto=rule, rng_seed=seed, verbose=False, **kw)
            agg.append((rows, s))
            print(json.dumps({"scenario": scen, "veto": rule, "seed": seed,
                              "windows": [(r["steps"], r["world"], r["reflex_rate"], r["reflex_acc"], r["answer_acc"], r["measurements_per_ask"]) for r in rows],
                              "wrong_reflex_after_drift": s["wrong_reflexes_after_drift_on_changed"],
                              "final": s["final_status_counts"], "final_known_correct": s["final_known_correct"]}))
        import numpy as np
        def m(i, j):
            v = [a[0][i][j] for a in agg if a[0][i][j] is not None]
            return round(float(np.mean(v)), 3)
        keys = ["reflex_rate", "reflex_acc", "answer_acc", "measurements_per_ask"]
        print(f"## MEAN {scen} {rule}: window -> " + " ; ".join(
            f"{agg[0][0][i]['steps']}({agg[0][0][i]['world']}): " + " ".join(f"{k[:8]}={m(i, k)}" for k in keys)
            for i in range(len(agg[0][0]))))
        print(f"## MEAN {scen} {rule}: wrong_reflex_after_drift={np.mean([a[1]['wrong_reflexes_after_drift_on_changed'] for a in agg]):.1f} "
              f"final_known={np.mean([a[1]['final_status_counts'].get('known',0) for a in agg]):.1f}/37 "
              f"final_known_correct={np.mean([a[1]['final_known_correct'] for a in agg]):.1f}", flush=True)
