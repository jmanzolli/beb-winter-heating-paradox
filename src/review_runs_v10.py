"""Route 52 solves requested by the review of 2026-11-09.

Modes (one per process; results go to CAMP_OUT):
  capex     M1. Heater installed capital at REVIEW_CAPEX (CAD per heater,
            comma list), at lambda = 0 (the basis of D0), absolute gap
            1 kCAD/yr. Each solve is MIP-started from the archived lambda = 0
            design that is cheapest at that heater price: every archived
            design's cost is F1 + n_FFH x price x CRF_BUS, because the heater
            capital is the only term that changes. The archived lambda = 100
            runs (5-15 kCAD) left the 15 kCAD case on a 6-FFH incumbent that
            the 18-FFH design beats.
  ddeval    M8. The severe-band design-day design (det_designday, solved on
            151 severe days) re-evaluated on the full scenario set with its
            first stage fixed, at lambda = 0; recorded as "det_designday_eval".
  d0eval    Same fixed-design evaluation for D0 (econ_lam0), so both designs
            are dispatched by the identical procedure; "econ_lam0_eval".

Run: ROUTE_INPUTS=route52_inputs_v9.json CAMP_OUT=<file> \
     REVIEW_SRC=campaign_v9rev_results.json python review_runs_v10.py <mode>
"""
import json
import os
import sys

import campaign_v5 as C
import route52_prototype as R

mode = sys.argv[1]
SRC = {r["label"]: r for r in json.load(open(os.environ.get(
    "REVIEW_SRC", "campaign_v9rev_results.json")))["runs"]}

if mode == "capex":
    # lambda = 0 candidates: the economic baseline and the cap frontier
    cand = [r for l, r in SRC.items()
            if r.get("lam") == 0.0 and "F1" in r and r.get("n_ffh") is not None
            and (l == "econ_lam0" or l.startswith("eps_"))]
    for fc in [float(v) for v in os.environ.get(
            "REVIEW_CAPEX", "15000,17500,20000,25000,30000").split(",")]:
        best = min(cand, key=lambda r: r["F1"] + r["n_ffh"] * fc * R.CRF_BUS)
        print(f"capex {fc:.0f}: MIP start {best['label']} "
              f"({best['n_ffh']} FFH, est. F1 "
              f"{(best['F1'] + best['n_ffh'] * fc * R.CRF_BUS) / 1e3:,.1f} kCAD/yr)",
              flush=True)
        f, g = C.set_ffh_capex(fc)
        C.solve(f"ffh_capex_l0_{int(fc)}", lam=0.0, mods=f, unmods=g,
                tlim=C.TLIM_HARD, abs_gap=1000.0,
                mip_start=C.design_from_record(best))
elif mode in ("ddeval", "d0eval"):
    src = ({r["label"]: r for r in json.load(open(os.environ.get(
        "REVIEW_DD", "rev_designday_v9.json")))["runs"]}["det_designday"]
           if mode == "ddeval" else SRC["econ_lam0"])
    lbl = "det_designday_eval" if mode == "ddeval" else "econ_lam0_eval"
    C.solve(lbl, lam=0.0, fix_design=C.design_from_record(src),
            tlim=C.TLIM_HARD, abs_gap=100.0)
else:
    raise SystemExit(f"unknown mode {mode}")
C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
          f"ffh {r['n_ffh']} co2 {r['co2_t']} ch {r['chargers']}", flush=True)
