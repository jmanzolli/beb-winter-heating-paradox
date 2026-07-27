"""
Near-optimal equipment ranges at division scale (protocol 5.4), warm started.

The first attempt returned None for every target. The reason was structural,
not a limit that needed raising: each stability problem changes the objective
to an equipment count, adds a cost cap, and was then solved from scratch on a
183-block model in 3,600 s -- when case D itself needed 7,200 s merely to find
an incumbent. Without a starting solution the solver never reached one.

Here a feasible starting point is constructed once and reused for all six
problems:

  1. fix the first stage to the recorded coordinated design and solve only the
     recourse (fast: the hard combinatorics are in the first stage);
  2. that solution satisfies the cost cap by construction, since its cost is
     the reference cost itself;
  3. seed every min/max problem with it.

Reported as a RANGE, not a point: if very different equipment counts are all
within tau of the best known cost, presenting one of them as the answer would
overstate what the optimization establishes.

Usage:
  ROUTE_INPUTS=garage_inputs_v5.json DIV_OUT=div_stab_ws.json \
  DIV_THREADS=24 python3 stability_v6.py [tau_kCAD]
"""

import json
import os
import sys
import time

os.environ.setdefault("ROUTE_INPUTS", "garage_inputs_v5.json")

import gurobipy as gp
from gurobipy import GRB

import campaign_division_v5 as D
import route52_prototype as R

OUT_FILE = os.environ.get("DIV_OUT", "div_stab_ws.json")
SRC = os.environ.get("DIV_SRC", "campaign_division_v5.json")
TAU = float(sys.argv[1]) * 1e3 if len(sys.argv) > 1 else D.TAU
TLIM = int(os.environ.get("DIV_TLIM", 7200))
K = range(len(R.BUS_CLASSES))


def design_from(rec):
    name2k = {bc.name: k for k, bc in enumerate(R.BUS_CLASSES)}
    x = {k: 0 for k in K}
    for nm, c in rec["fleet"].items():
        x[name2k[nm]] = c
    wch = {(n, p): 0 for n in R.SITES for p in R.CH_CLASSES}
    for key, c in rec["chargers"].items():
        n, p = key.split(":")
        wch[(n, int(p))] = c
    ysite = {k: (1 if v > 0 else 0) for k, v in wch.items()}
    ygrid = {(n, j): 0 for n in R.SITES for j in range(len(R.GRID_TIERS))}
    for n, kw in rec.get("grid_kW", {}).items():
        for j, g in enumerate(R.GRID_TIERS):
            if abs(g - kw) < 1e-6:
                ygrid[(n, j)] = 1
    return {"x": x, "wch": wch, "ysite": ysite, "ygrid": ygrid}


def build(pin=None):
    m = R.build_model(carbon_price_t=D.LAM, fix_fleet_total=True,
                      diff_objective=True)
    h = m._handles
    if pin:
        for k in K:
            m.addConstr(h["x"][k] == pin["x"][k])
        for n in R.SITES:
            for p in R.CH_CLASSES:
                m.addConstr(h["wch"][n, p] == pin["wch"][(n, p)])
                m.addConstr(h["ysite"][n, p] == pin["ysite"][(n, p)])
            for j in range(len(R.GRID_TIERS)):
                m.addConstr(h["ygrid"][n, j] == pin["ygrid"][(n, j)])
    return m


def snapshot(m):
    h = m._handles
    return {"x": {k: round(h["x"][k].X) for k in K},
            "wch": {(n, p): round(h["wch"][n, p].X)
                    for n in R.SITES for p in R.CH_CLASSES},
            "ysite": {(n, p): round(h["ysite"][n, p].X)
                      for n in R.SITES for p in R.CH_CLASSES},
            "ygrid": {(n, j): round(h["ygrid"][n, j].X)
                      for n in R.SITES for j in range(len(R.GRID_TIERS))},
            "z": {w: {key: round(v.X) for key, v in m._scen[w]["z"].items()}
                  for w in R.SCEN}}


def seed(m, sol):
    h = m._handles
    for k in K:
        h["x"][k].Start = sol["x"][k]
    for n in R.SITES:
        for p in R.CH_CLASSES:
            h["wch"][n, p].Start = sol["wch"][(n, p)]
            h["ysite"][n, p].Start = sol["ysite"][(n, p)]
        for j in range(len(R.GRID_TIERS)):
            h["ygrid"][n, j].Start = sol["ygrid"][(n, j)]
    for w in R.SCEN:
        for key, v in m._scen[w]["z"].items():
            v.Start = sol["z"][w][key]


TARGETS = {
    "n_ffh": lambda h: gp.quicksum(h["x"][k] for k in K
                                   if R.BUS_CLASSES[k].ffh),
    "n_ext": lambda h: gp.quicksum(h["x"][k] for k in K
                                   if R.BUS_CLASSES[k].batt_nom > 600),
    "n_opp": lambda h: gp.quicksum(h["wch"][n, p] for n in R.SITES
                                   for p in R.CH_CLASSES if n != "depot"),
}

if __name__ == "__main__":
    t0 = time.time()
    src = json.load(open(SRC))
    rec = src["cases"]["D_full_coordination"]
    pin = design_from(rec)
    print(f"reference design: {rec['fleet']} | diff cost "
          f"{rec['differentiating_cost']/1e3:.1f}k | tau {TAU/1e3:.0f}k",
          flush=True)

    # 1. recover a complete feasible solution on the recorded design
    m0 = build(pin=pin)
    D.limits(m0, "stab_seed", tlim=1800, gap=5000.0)
    m0.optimize()
    assert m0.SolCount > 0, "could not recover a feasible reference solution"
    ref_cost = m0._total_cost.getValue()
    sol = snapshot(m0)
    print(f"reference recourse recovered: cost {ref_cost/1e3:.1f}k "
          f"({m0.Runtime:.0f}s)", flush=True)

    out = {"tau": TAU, "reference_cost": round(ref_cost, 1),
           "reference_fleet": rec["fleet"], "tlim": TLIM, "results": {}}
    for name, expr in TARGETS.items():
        for sense, tag in ((GRB.MINIMIZE, "min"), (GRB.MAXIMIZE, "max")):
            lbl = f"stab_{name}_{tag}"
            m = build()
            m.addConstr(m._total_cost <= ref_cost + TAU, name="cost_cap")
            seed(m, sol)
            m.setObjective(expr(m._handles), sense)
            D.limits(m, lbl, tlim=TLIM, gap=0.5)
            m.optimize()
            if m.SolCount == 0:
                print(lbl, "-> NO SOLUTION (status", m.Status, ")", flush=True)
                out["results"][lbl] = None
            else:
                out["results"][lbl] = {
                    "value": round(m.ObjVal, 2),
                    "bound": round(m.ObjBound, 2),
                    "status": int(m.Status), "time_s": round(m.Runtime, 1)}
                print(f"{lbl} -> {m.ObjVal:.0f} (bound {m.ObjBound:.1f}, "
                      f"{m.Runtime:.0f}s)", flush=True)
            json.dump(out, open(OUT_FILE, "w"), indent=1)

    print("\n--- near-optimal ranges within "
          f"{TAU/1e3:.0f} kCAD of {ref_cost/1e3:.1f}k ---", flush=True)
    for name in TARGETS:
        lo = out["results"].get(f"stab_{name}_min")
        hi = out["results"].get(f"stab_{name}_max")
        if lo and hi:
            print(f"  {name}: {lo['value']:.0f} .. {hi['value']:.0f}",
                  flush=True)
    out["minutes"] = round((time.time() - t0) / 60, 1)
    json.dump(out, open(OUT_FILE, "w"), indent=1)
    print("done in", out["minutes"], "min", flush=True)
