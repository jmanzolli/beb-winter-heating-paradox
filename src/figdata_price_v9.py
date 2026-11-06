"""Hourly site load of fixed Route 52 designs, for the price-response figure.

Re-solves the second stage with the first stage of each listed design fixed
(lambda = 0, 1% gap, 900 s; a diagnostic, not a certified-cost claim) and
records, per scenario, the depot load (charging + preconditioning) and the
summed terminal charging per 15-min step, together with the hourly energy
price the model uses.

Run: ROUTE_INPUTS=route52_inputs_v9.json FIGD_RES=campaign_v9_results.json \
     FIGD_OUT=figdata_price_v9.json python figdata_price_v9.py
"""
import json
import os

import route52_prototype as R
from campaign_v5 import design_from_record

RES = os.environ.get("FIGD_RES", "campaign_v9_results.json")
OUT = os.environ.get("FIGD_OUT", "figdata_price_v9.json")
LABELS = os.environ.get("FIGD_LABELS", "econ_lam0,eps_0.00").split(",")
runs = {r["label"]: r for r in json.load(open(RES))["runs"]}

out = {"dt_h": R.DT, "t0_h": R.T0,
       "hours": [R.step_hour(t) for t in R.STEPS],
       "price": {w: [R.tou(t, w) for t in R.STEPS] for w in R.SCEN},
       "designs": {}}
for lb in LABELS:
    d = design_from_record(runs[lb])
    m = R.build_model(carbon_price_t=0.0)
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
    m.Params.MIPGap = 0.01
    m.Params.TimeLimit = 900
    m.Params.Threads = int(os.environ.get("CAMP_THREADS", 8))
    m.optimize()
    assert m.SolCount > 0, lb
    rec = {"chargers": runs[lb]["chargers"], "n_ffh": runs[lb]["n_ffh"],
           "obj": m.ObjVal, "scen": {}}
    for w in R.SCEN:
        s = m._scen[w]
        dep, term = [], []
        for t in R.STEPS:
            dv = sum(s["c"][b, "depot", t].X for b in range(R.N_BLOCKS)
                     if (b, "depot", t) in s["c"])
            dv += sum(s["ppre"][b, t].X for b in range(R.N_BLOCKS)
                      if (b, t) in s["ppre"])
            tv = sum(s["c"][b, n, t].X for b in range(R.N_BLOCKS)
                     for n in R.SITES if n != "depot" and (b, n, t) in s["c"])
            dep.append(round(dv, 2))
            term.append(round(tv, 2))
        rec["scen"][w] = {"depot_kW": dep, "terminal_kW": term}
    out["designs"][lb] = rec
    print(lb, "obj", round(m.ObjVal), flush=True)
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
