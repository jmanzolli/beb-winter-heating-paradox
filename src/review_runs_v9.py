"""Additional Route 52 solves requested by the 2026-11-06 internal review.

Modes (one per process; results go to CAMP_OUT):
  capex       FFH installed-capital bisection at 7.5, 10 and 12.5 kCAD/heater
              (lambda = 100, as the existing 5 and 15 kCAD runs)
  d3          re-run the lexicographic phase 2 of the eps_0.10 cap with a MIP
              start from lam_5000, which dominates the archived eps_0.10
              design; recorded as "eps_0.10r"
  designday   deterministic design-day benchmark: all 151 winter days at the
              severe band (-17.5 C) plus the off-season day; recorded as
              "det_designday"

Run: ROUTE_INPUTS=route52_inputs_v9.json CAMP_OUT=<file> \
     REVIEW_SRC=campaign_v9_results.json python review_runs_v9.py <mode>
"""
import json
import os
import sys

import campaign_v5 as C
import route52_prototype as R

mode = sys.argv[1]
SRC = {r["label"]: r for r in json.load(open(os.environ.get(
    "REVIEW_SRC", "campaign_v9_results.json")))["runs"]}

if mode == "capex":
    for fc in [float(v) for v in os.environ.get(
            "REVIEW_CAPEX", "7500,10000,12500").split(",")]:
        f, g = C.set_ffh_capex(fc)
        C.solve(f"ffh_capex_{int(fc)}", lam=100.0, mods=f, unmods=g)
elif mode == "d3":
    r0 = SRC["eps_0.10"]
    C.solve("eps_0.10r", eps=r0["eps"], lam=0.0, lexicographic=True,
            tlim=C.TLIM_HARD, force=True,
            mip_start=C.design_from_record(SRC["lam_5000"]))
elif mode == "designday":
    T_sev = R.SCEN["severe"][0]
    off = {w: R.SCEN[w] for w in R.SCEN if w in R.HEATLESS}
    scen0 = dict(R.SCEN)
    def f():
        R.SCEN.clear()
        R.SCEN["severe"] = (T_sev, 151)
        R.SCEN.update(off)
    def g():
        R.SCEN.clear()
        R.SCEN.update(scen0)
    C.solve("det_designday", lam=100.0, mods=f, unmods=g)
else:
    raise SystemExit(f"unknown mode {mode}")
C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
          f"ffh {r['n_ffh']} co2 {r['co2_t']} ch {r['chargers']}", flush=True)
