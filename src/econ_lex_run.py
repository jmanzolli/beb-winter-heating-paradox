"""Re-solve the economic baseline lexicographically, and keep the result.

Two defects in the recorded econ_lam0 motivate this:

1. The H2 pass found a cheaper baseline (3,137,512.6 against the recorded
   3,137,990.9) and the old dedup rule discarded it for having a 5 CAD wider
   gap. bp_lam_1032 independently records a feasible design at 3,137,466.3,
   so the recorded baseline is provably not optimal and every increment
   measured against it is overstated.

2. At lambda = 0 the dispatch is cost-indifferent, so the reported emissions
   are whichever tie the solver happened to pick: the same first-stage design
   shows 22.070 t under econ_lam0 and 20.678 t under bp_lam_1032. The frontier
   points get a lexicographic phase 2 to resolve this; the baseline never did.

Phase 1 minimises F1 under a deliberately non-binding cap, phase 2 minimises
emissions subject to F1 <= F1* + LEX_TOL. Warm-started from the cheapest
recorded design.

Run: ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=campaign_v8_results.json \
     python econ_lex_run.py
"""
import campaign_v5 as C

CAP = 1e6  # tonnes: far above any feasible value, so phase 1 is unconstrained

cands = [r for r in (C.DONE.get(l) for l in
                     ("bp_lam_1032", "lam_1000", "econ_lam0")) if r]
start = min(cands, key=lambda r: r.get("F1", 9e18)) if cands else None
if start:
    print(f"warm start from {start['label']} (F1 {start['F1']:.1f})")

C.solve("econ_lam0", eps=CAP, lam=0.0, lexicographic=True,
        tlim=C.TLIM_HARD, force=True,
        mip_start=C.design_from_record(start) if start else None)
C.dedup_runs()

rec = {r["label"]: r for r in C.OUT["runs"]}["econ_lam0"]
print(f"econ_lam0 now F1={rec['F1']:.1f} lb={rec.get('lb')} "
      f"gap={rec.get('abs_gap')} co2={rec['co2_t']}")
