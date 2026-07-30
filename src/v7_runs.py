"""v7 traction-interface re-runs: baseline, zero-cap, +-10% traction.
Usage: ROUTE_INPUTS=route52_inputs_v7.json CAMP_OUT=v7_results.json python3 v7_runs.py
"""
import os
assert os.environ.get("ROUTE_INPUTS", "").endswith("v7.json"), "set ROUTE_INPUTS to the v7 instance"
import campaign_v5 as C
import route52_prototype as R

def lm(f):
    return {(w, b, i): (f, 1.0) for w in R.SCEN for b in range(R.N_BLOCKS)
            for i in range(len(R.BLOCKS[b].trips))}

C.solve("v7_econ_lam0", lam=0.0, force=True)
C.solve("v7_eps_0.00", eps=0.0, lam=0.0, force=True)
C.solve("v7_tr_minus10", lam=0.0, force=True, load_mult=lm(0.9))
C.solve("v7_tr_plus10", lam=0.0, force=True, load_mult=lm(1.1))
print("v7 runs complete")
