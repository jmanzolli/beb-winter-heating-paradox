"""
Warm-started re-solve of division cases B, C and D.

The first pass produced differentiating costs of 2,760.7k (B), 2,715.1k (C)
and 2,784.9k (D) with absolute gaps of 210-280 kCAD. D costing more than C is
impossible at optimality: D is exactly C with the scenario-invariant
assignment constraint removed, so D's feasible set contains C's and its
optimum cannot be worse. The ordering was an artifact of gaps far larger than
the coordination effect being measured.

Fix: solve C first, then seed D with C's COMPLETE solution -- first stage and
the per-scenario block-class assignment. That solution is feasible for D by
construction, so D's incumbent is bounded above by C's and the ordering
violation cannot recur. B is reseeded from its own recorded incumbent.

Nesting that must hold (checked and reported at the end):
    D <= C   and   D <= B      (both are restrictions of D)
B and C are NOT nested with each other -- B adds route-locked fleets, C adds
frozen assignment -- so their order carries no information either way.

A rigorous claim that coordination pays requires D's incumbent to fall below
C's certified LOWER BOUND. If it does not, the comparison is reported as
inconclusive at the achieved tolerance rather than asserted.

Usage:
  ROUTE_INPUTS=garage_inputs_v5.json DIV_TLIM=14400 python3 rerun_div_v6.py
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

OUT_FILE = os.environ.get("DIV_OUT", "campaign_division_v5.json")
TLIM = int(os.environ.get("DIV_TLIM", 14400))


def full_solution(m):
    """First stage plus per-scenario assignment, for use as a MIP start."""
    h = m._handles
    return {
        "x": {k: round(h["x"][k].X) for k in range(len(R.BUS_CLASSES))},
        "wch": {(n, p): round(h["wch"][n, p].X)
                for n in R.SITES for p in R.CH_CLASSES},
        "ysite": {(n, p): round(h["ysite"][n, p].X)
                  for n in R.SITES for p in R.CH_CLASSES},
        "ygrid": {(n, j): round(h["ygrid"][n, j].X)
                  for n in R.SITES for j in range(len(R.GRID_TIERS))},
        "z": {w: {key: round(v.X) for key, v in m._scen[w]["z"].items()}
              for w in R.SCEN},
    }


def apply_start(m, sol):
    h = m._handles
    for k in range(len(R.BUS_CLASSES)):
        h["x"][k].Start = sol["x"][k]
    for n in R.SITES:
        for p in R.CH_CLASSES:
            h["wch"][n, p].Start = sol["wch"][(n, p)]
            h["ysite"][n, p].Start = sol["ysite"][(n, p)]
        for j in range(len(R.GRID_TIERS)):
            h["ygrid"][n, j].Start = sol["ygrid"][(n, j)]
    if "z" in sol:
        for w in R.SCEN:
            zs = sol["z"].get(w)
            if not zs:
                continue
            for key, v in m._scen[w]["z"].items():
                if key in zs:
                    v.Start = zs[key]


def solve(label, freeze_z=False, route_lock=False, start=None):
    m = R.build_model(carbon_price_t=D.LAM, fix_fleet_total=True,
                      diff_objective=True)
    if freeze_z:
        W = list(R.SCEN.keys())
        z0 = m._scen[W[0]]["z"]
        for w in W[1:]:
            zw = m._scen[w]["z"]
            for key in z0:
                m.addConstr(zw[key] == z0[key])
    if route_lock:
        routes = sorted({D.route_of(R.BLOCKS[b].branch)
                         for b in range(R.N_BLOCKS)})
        K = range(len(R.BUS_CLASSES))
        xr = m.addVars(routes, K, vtype=GRB.INTEGER, lb=0, name="x_route")
        h = m._handles
        for k in K:
            m.addConstr(gp.quicksum(xr[r, k] for r in routes) == h["x"][k])
        for w in R.SCEN:
            z = m._scen[w]["z"]
            for r in routes:
                br = [b for b in range(R.N_BLOCKS)
                      if D.route_of(R.BLOCKS[b].branch) == r]
                for k in K:
                    m.addConstr(gp.quicksum(z[b, k] for b in br) <= xr[r, k])
    if start:
        apply_start(m, start)
    D.limits(m, label, tlim=TLIM)
    m.optimize()
    if m.SolCount == 0:
        print(label, "-> NO SOLUTION", m.Status, flush=True)
        return None, None
    rec = D.summarize(m, label)
    rec["lb_diff"] = round(rec["obj_solver"] - rec["abs_gap"], 1)
    print(f"{label} -> diff {rec['differentiating_cost']/1e3:.1f}k "
          f"| solver {rec['obj_solver']/1e3:.1f}k bound "
          f"{rec['lb_diff']/1e3:.1f}k gap {rec['abs_gap']:.0f} "
          f"| ffh {rec['n_ffh']} | {rec['time_s']:.0f}s", flush=True)
    return rec, m


if __name__ == "__main__":
    t0 = time.time()
    out = json.load(open(OUT_FILE)) if os.path.exists(OUT_FILE) else {"cases": {}}
    prev = out.get("cases", {})
    print(f"warm-started division re-solve | TLIM={TLIM}s", flush=True)

    # 1. C first: frozen assignment collapses the scenario symmetry and is the
    #    easiest of the three to get a good incumbent for.
    # (C is solved from scratch; its own recorded incumbent was produced by a
    # different formulation pass and is not reused)
    recC, mC = solve("C_shared_infra_frozen_z_ws", freeze_z=True)
    if recC:
        out["cases"]["C_shared_infra_frozen_z"] = recC
        json.dump(out, open(OUT_FILE, "w"), indent=1)

    # 2. D seeded with C's complete solution -- feasible for D by
    #    construction, so D's incumbent cannot exceed C's.
    solC = full_solution(mC) if mC is not None else None
    recD, mD = solve("D_full_coordination_ws", start=solC)
    if recD:
        out["cases"]["D_full_coordination"] = recD
        json.dump(out, open(OUT_FILE, "w"), indent=1)

    # 3. B reseeded from D's solution where it is admissible; B adds
    #    route-locked pools, which D's assignment need not satisfy, so the
    #    start is advisory only (Gurobi repairs or discards it).
    recB, mB = solve("B_shared_infra_route_locked_ws", route_lock=True,
                     start=full_solution(mD) if mD is not None else None)
    if recB:
        out["cases"]["B_shared_infra_route_locked"] = recB
        json.dump(out, open(OUT_FILE, "w"), indent=1)

    # 4. nesting check + whether the coordination claim is certifiable
    print("\n--- nesting (must hold: D <= C and D <= B) ---", flush=True)
    ok = True
    for other, rec in (("C", recC), ("B", recB)):
        if recD and rec:
            d, o = recD["differentiating_cost"], rec["differentiating_cost"]
            good = d <= o + 1.0
            ok &= good
            print(f"D ({d/1e3:.1f}k) <= {other} ({o/1e3:.1f}k): "
                  f"{'OK' if good else 'VIOLATED'}", flush=True)
            lb = rec["lb_diff"]
            if d < lb:
                print(f"  certified: D beats {other} by at least "
                      f"{(lb - d)/1e3:.1f} kCAD (D incumbent < {other} bound)",
                      flush=True)
            else:
                print(f"  NOT certified: D incumbent {d/1e3:.1f}k is above "
                      f"{other}'s lower bound {lb/1e3:.1f}k -- the difference "
                      f"is within the optimality gap and no claim is "
                      f"supported", flush=True)
    out["nesting_ok"] = bool(ok)
    out["meta"] = dict(out.get("meta", {}),
                       rerun_minutes=round((time.time() - t0) / 60, 1),
                       rerun_tlim=TLIM, warm_started=True)
    json.dump(out, open(OUT_FILE, "w"), indent=1)
    print("\ndone in", out["meta"]["rerun_minutes"], "min", flush=True)
