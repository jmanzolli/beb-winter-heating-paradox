"""Per-band dispatch feasibility of the mean-temperature-benchmark design
and the economic baseline: first stage fixed, one band at a time, elastic
slack measures any shortfall (0 = feasible).

Usage:
  ROUTE_INPUTS=<inputs.json> DETBAND_RES=<campaign results> \
  DETBAND_OUT=<out.json> python detband_check.py
"""
import json
import os

import campaign_v5 as C
import route52_prototype as R

RESF = os.environ["DETBAND_RES"]
OUTF = os.environ["DETBAND_OUT"]
runs = {r["label"]: r for r in json.load(open(RESF))["runs"]
        if "error" not in r and not r.get("infeasible")}
out = {}
for lbl in ("det_meanT", "econ_lam0"):
    if lbl not in runs:
        print("missing", lbl)
        continue
    d = C.design_from_record(runs[lbl])
    out[lbl] = {}
    for w in R.SCEN:
        m = R.build_model(carbon_price_t=0.0, elastic=True, only_scen=w)
        h = m._handles
        for k in range(len(R.BUS_CLASSES)):
            m.addConstr(h["x"][k] == d["x"][k])
        for n in R.SITES:
            for p in R.CH_CLASSES:
                m.addConstr(h["wch"][n, p] == d["wch"][(n, p)])
                m.addConstr(h["ysite"][n, p] == d["ysite"][(n, p)])
            for j in range(len(R.GRID_TIERS)):
                m.addConstr(h["ygrid"][n, j] == d["ygrid"][(n, j)])
        m.Params.OutputFlag = 0
        m.Params.MIPGap = 0.002
        m.Params.TimeLimit = 600
        m.Params.Threads = 4
        m.optimize()
        if m.SolCount == 0:
            out[lbl][w] = {"solved": False, "feasible": False,
                           "shortfall_kWh": None, "T": R.SCEN[w][0]}
        else:
            sh = float(m._shortfall.getValue())
            out[lbl][w] = {"solved": True, "shortfall_kWh": round(sh, 1),
                           "feasible": bool(sh < 0.1), "T": R.SCEN[w][0]}
        print(lbl, w, out[lbl][w], flush=True)
        json.dump(out, open(OUTF, "w"), indent=1)
print("detband done")
