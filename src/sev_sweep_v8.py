"""Severe-band traction-factor sensitivity under the v8 inputs.

The adopted f_severe = 1.224 rests on four fleet-wide runs, so the planning
factor for the most damaging band is the thinnest empirical input. This
re-solves the economic baseline and the FFH-free endpoint with f_severe at
1.15 and 1.30, everything else at v8 values.

Run: ROUTE_INPUTS=route52_inputs_v8_sev115.json CAMP_OUT=sev115_v8.json \
     python sev_sweep_v8.py     (and likewise for sev130)
"""
import campaign_v5 as C

C.solve("econ_lam0", lam=0.0, tlim=C.TLIM)
C.solve("eps_0.00", eps=0.0, lam=0.0, lexicographic=True, tlim=C.TLIM)
C.dedup_runs()
for r in C.OUT["runs"]:
    print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap',0):,.0f} "
          f"ffh {r['n_ffh']} co2 {r['co2_t']} ch {r['chargers']}")
