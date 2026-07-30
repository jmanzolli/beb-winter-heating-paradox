"""
Division-scale coordination counterfactuals (revision protocol Section 5.3-5.4).

The previous draft compared Route 52 with the Arrow Road division. Those are
different route systems, so the comparison cannot isolate coordination. This
script runs four cases on the SAME 14-route, 183-block division system:

  A  fragmented: every route optimized independently (own depot chargers,
     own grid tier, own fleet); results summed.
  B  shared infrastructure, route-locked fleets: one division-wide
     infrastructure plan, but each route's blocks may only be served by
     buses procured for that route (no cross-route class pooling).
  C  shared infrastructure and shared fleet pool, scenario-invariant
     assignment (z frozen across weather scenarios).
  D  full coordination: shared infrastructure, shared pool, and
     scenario-adaptive assignment.

Then near-optimal stability (protocol 5.4): with differentiating cost
F <= F* + tau, minimize and maximize FFH-equipped buses, opportunity
chargers, and extended-battery buses.

All cases use the differentiating-cost objective (common 183-bus base cost
removed from the solver objective, added back for reporting) so the reported
gap is meaningful relative to the decisions under study.

Usage:
  ROUTE_INPUTS=garage_inputs_v5.json python3 campaign_division_v5.py [cases]
  e.g. ... campaign_division_v5.py A B C D stability
"""

import json
import os
import re
import sys
import time

os.environ.setdefault("ROUTE_INPUTS", "garage_inputs_v5.json")

import gurobipy as gp
from gurobipy import GRB

import route52_prototype as R

LAM = float(os.environ.get("DIV_LAM", 0.0))   # economic case; 100 = policy
ABS_GAP = float(os.environ.get("DIV_ABS_GAP", 2000.0))   # on DIFFERENTIATING cost
TLIM = int(os.environ.get("DIV_TLIM", 7200))
TLIM_SUB = int(os.environ.get("DIV_TLIM_SUB", 1800))  # per-route subproblem (case A)
TAU = float(os.environ.get("DIV_TAU", 25_000.0))  # stability tol on diff cost
LOGDIR = os.environ.get("DIV_LOGDIR", "logs_div_v5")
NODEDIR = "gurobi_nodefiles"
# Sized for a 16 GB / 8-core laptop by default. On a larger host raise these
# with DIV_THREADS and DIV_MEM_GB rather than editing the file, so the run
# stays reproducible from the environment record.
THREADS = int(os.environ.get("DIV_THREADS", 6))
NODEFILE_GB = float(os.environ.get("DIV_NODEFILE_GB", 1.0))
MEM_GB = float(os.environ.get("DIV_MEM_GB", 11.0))
os.makedirs(LOGDIR, exist_ok=True)
os.makedirs(NODEDIR, exist_ok=True)

# One file per process. Cases are independent MILPs, so on a many-core host
# they can run as concurrent processes -- but only if each writes its own
# result file, otherwise the last dump wins and earlier cases are lost.
# Merge the shards afterwards with merge_division.py.
OUT_FILE = os.environ.get("DIV_OUT", "campaign_division_v5.json")
OUT = json.load(open(OUT_FILE)) if os.path.exists(OUT_FILE) else {"cases": {}}


def dump():
    json.dump(OUT, open(OUT_FILE, "w"), indent=1)


def limits(m, label, tlim=TLIM, gap=ABS_GAP):
    m.Params.OutputFlag = 0
    m.Params.LogFile = f"{LOGDIR}/{label}.log"
    m.Params.MIPGapAbs = gap
    m.Params.TimeLimit = tlim
    m.Params.Threads = THREADS
    m.Params.NodefileStart = NODEFILE_GB
    m.Params.NodefileDir = NODEDIR
    m.Params.SoftMemLimit = MEM_GB


def route_of(branch_name):
    """'r52_E0' -> '52'."""
    mt = re.match(r"r(\d+)", branch_name)
    return mt.group(1) if mt else branch_name


def summarize(m, label, extra=None):
    h = m._handles
    K = range(len(R.BUS_CLASSES))
    J = range(len(R.GRID_TIERS))
    bus_full = R.CRF_BUS * sum(R.BUS_CLASSES[k].cost * h["x"][k].X for k in K)
    ch = (R.CRF_CH * sum(R.charger_cost(p) * h["wch"][n, p].X
                         for n in R.SITES for p in R.CH_CLASSES)
          + R.CRF_CH * R.SITE_FIXED_COST * sum(
              h["ysite"][n, p].X for n in R.SITES for p in R.CH_CLASSES
              if n != "depot"))
    grid = R.CRF_GRID * sum(R.GRID_TIER_COST[j] * h["ygrid"][n, j].X
                            for n in R.SITES for j in J)
    dem = h["demand_annual"].getValue()
    en = sum(R.SCEN[w][1] * m._scen[w]["energy_cost"].getValue() for w in R.SCEN)
    om = R.FFH_ANNUAL_OM * sum(h["x"][k].X for k in K if R.BUS_CLASSES[k].ffh)
    dL = sum(R.SCEN[w][1] * m._scen[w]["D"].X for w in R.SCEN)
    batt_inc = R.CRF_BUS * sum((R.BUS_CLASSES[k].cost - R.BUS_BASE)
                               * h["x"][k].X for k in K)
    d = {"label": label,
         "obj_solver": round(m.ObjVal, 1), "lb_solver": round(m.ObjBound, 1),
         "abs_gap": round(m.ObjVal - m.ObjBound, 1),
         "rel_gap_diff_cost": round(abs(m.ObjVal - m.ObjBound)
                                    / max(1.0, abs(m.ObjVal)), 6),
         "time_s": round(m.Runtime, 1), "status": int(m.Status),
         "total_annual_cost": round(bus_full + ch + grid + dem + en + om
                                    + R.DIESEL_PRICE * dL, 1),
         "differentiating_cost": round(batt_inc + ch + grid + dem + en + om
                                       + R.DIESEL_PRICE * dL, 1),
         "cost_parts": {"battery_increment": round(batt_inc, 1),
                        "charger_site_capital": round(ch, 1),
                        "grid_capital": round(grid, 1),
                        "demand_charges": round(dem, 1),
                        "electricity": round(en, 1),
                        "ffh_om": round(om, 1),
                        "diesel_cost": round(R.DIESEL_PRICE * dL, 1)},
         "n_buses": int(round(sum(h["x"][k].X for k in K))),
         "n_ffh": int(round(sum(h["x"][k].X for k in K
                                if R.BUS_CLASSES[k].ffh))),
         "n_ext": int(round(sum(h["x"][k].X for k in K
                                if R.BUS_CLASSES[k].batt_nom > 600))),
         "fleet": {R.BUS_CLASSES[k].name: int(round(h["x"][k].X))
                   for k in K if h["x"][k].X > 0.5},
         "chargers": {f"{n}:{p}": int(round(h["wch"][n, p].X))
                      for n in R.SITES for p in R.CH_CLASSES
                      if h["wch"][n, p].X > 0.5},
         "n_opp_chargers": int(round(sum(h["wch"][n, p].X for n in R.SITES
                                         for p in R.CH_CLASSES
                                         if n != "depot"))),
         "grid_kW": {n: round(h["g_add"][n].getValue(), 0) for n in R.SITES
                     if h["g_add"][n].getValue() > 1},
         "peak_depot_kW": round(max(h["rho"]["depot", l].X
                                    for l in ("win", "off")), 1),
         "diesel_L": round(dL, 1),
         "co2_t": round(dL * R.CO2_PER_L / 1000.0, 3)}
    if extra:
        d.update(extra)
    return d


def _apply_start(m, rec):
    """MIP-start the first-stage variables from a stored case record.

    DIV_START_FROM=<file>:<case> injects a known-good coordinated design
    (e.g. case C, which is feasible for D by construction) so a re-run
    does not depend on the root heuristic finding a usable incumbent.
    """
    h = m._handles
    name2k = {bc.name: k for k, bc in enumerate(R.BUS_CLASSES)}
    for k in range(len(R.BUS_CLASSES)):
        h["x"][k].Start = 0
    for name, cnt in rec["fleet"].items():
        h["x"][name2k[name]].Start = cnt
    for n in R.SITES:
        for p in R.CH_CLASSES:
            h["wch"][n, p].Start = 0
            h["ysite"][n, p].Start = 0
    for key, cnt in rec["chargers"].items():
        n, p = key.split(":")
        h["wch"][n, int(p)].Start = cnt
        h["ysite"][n, int(p)].Start = 1
    for n in R.SITES:
        for j in range(len(R.GRID_TIERS)):
            h["ygrid"][n, j].Start = 0
        kw = rec.get("grid_kW", {}).get(n)
        if kw:
            for j, g in enumerate(R.GRID_TIERS):
                if abs(g - kw) < 1e-6:
                    h["ygrid"][n, j].Start = 1
    print("MIP start injected from", rec["label"], flush=True)


def solve_case(label, freeze_z=False, route_lock=False, tlim=TLIM):
    m = R.build_model(carbon_price_t=LAM, fix_fleet_total=True,
                      diff_objective=True)
    sf = os.environ.get("DIV_START_FROM")
    if sf and not route_lock:
        fn, case = sf.rsplit(":", 1)
        rec0 = json.load(open(fn))["cases"].get(case)
        if rec0:
            _apply_start(m, rec0)
    if freeze_z:
        W = list(R.SCEN.keys())
        z0 = m._scen[W[0]]["z"]
        for w in W[1:]:
            zw = m._scen[w]["z"]
            for key in z0:
                m.addConstr(zw[key] == z0[key])
    if route_lock:
        # per-route fleet pools: x split into route-specific counts
        routes = sorted({route_of(R.BLOCKS[b].branch) for b in
                         range(R.N_BLOCKS)})
        K = range(len(R.BUS_CLASSES))
        xr = m.addVars(routes, K, vtype=GRB.INTEGER, lb=0, name="x_route")
        h = m._handles
        for k in K:
            m.addConstr(gp.quicksum(xr[r, k] for r in routes) == h["x"][k])
        for w in R.SCEN:
            z = m._scen[w]["z"]
            for r in routes:
                blocks_r = [b for b in range(R.N_BLOCKS)
                            if route_of(R.BLOCKS[b].branch) == r]
                for k in K:
                    m.addConstr(gp.quicksum(z[b, k] for b in blocks_r)
                                <= xr[r, k])
    limits(m, label, tlim=tlim)
    m.optimize()
    if m.SolCount == 0:
        print(label, "-> NO SOLUTION", m.Status, flush=True)
        return None, None
    rec = summarize(m, label)
    print(label, "-> total", round(rec["total_annual_cost"] / 1e3, 1),
          "kCAD | diff", round(rec["differentiating_cost"] / 1e3, 1),
          "| ffh", rec["n_ffh"], "| gap", rec["abs_gap"], flush=True)
    return rec, m


def case_A():
    """Fragmented planning: each route optimized on its own instance."""
    base = json.load(open(os.environ["ROUTE_INPUTS"]))
    routes = sorted({route_of(b) for b in base["branches"]})
    agg = {"label": "A_fragmented", "per_route": {}}
    tot = {k: 0.0 for k in ("total_annual_cost", "differentiating_cost",
                            "diesel_L", "co2_t")}
    counts = {k: 0 for k in ("n_buses", "n_ffh", "n_ext", "n_opp_chargers")}
    chargers, gridkw = {}, {}
    worst_gap = 0.0
    for r in routes:
        brs = {k: v for k, v in base["branches"].items() if route_of(k) == r}
        sites = sorted({"depot"} | {v["site_west"] for v in brs.values()}
                       | {v["site_east"] for v in brs.values()})
        sub = dict(base)
        sub["branches"] = brs
        sub["sites"] = sites
        sub["instance_name"] = f"route_{r}_standalone"
        # route52_prototype resolves ROUTE_INPUTS against ITS OWN directory,
        # so the sub-instance must be written there, not into the cwd, or the
        # fragmented case breaks when the job is launched from elsewhere
        fn = f"_sub_route_{r}.json"
        json.dump(sub, open(os.path.join(os.path.dirname(
            os.path.abspath(R.__file__)), fn), "w"), indent=1)
        # reload the model module against the sub-instance
        os.environ["ROUTE_INPUTS"] = fn
        import importlib
        importlib.reload(R)
        # same objective basis as cases B-D (differentiating cost, fleet
        # total fixed at the route's block count) so the reported gaps are
        # comparable across cases rather than dominated by base bus cost
        m = R.build_model(carbon_price_t=LAM, fix_fleet_total=True,
                          diff_objective=True)
        limits(m, f"A_route_{r}", tlim=TLIM_SUB, gap=250.0)
        m.optimize()
        if m.SolCount == 0:
            print(f"A route {r} -> NO SOLUTION", flush=True)
            continue
        rec = summarize(m, f"A_route_{r}")
        agg["per_route"][r] = rec
        for k in tot:
            tot[k] += rec[k]
        for k in counts:
            counts[k] += rec[k]
        for kk, v in rec["chargers"].items():
            chargers[kk] = chargers.get(kk, 0) + v
        for n, v in rec["grid_kW"].items():
            gridkw[n] = gridkw.get(n, 0) + v
        worst_gap = max(worst_gap, rec["abs_gap"])
        print(f"  A route {r}: {rec['n_ffh']}/{rec['n_buses']} FFH, "
              f"diff {rec['differentiating_cost']/1e3:.1f} kCAD, "
              f"gap {rec['abs_gap']:.0f}", flush=True)
        OUT["cases"]["A_fragmented"] = agg
        dump()
    agg.update({k: round(v, 1) for k, v in tot.items()})
    agg.update(counts)
    agg["chargers"] = chargers
    agg["grid_kW"] = gridkw
    agg["worst_route_gap"] = worst_gap
    agg["note"] = ("sum of 14 independent route optima; no shared terminal "
                   "chargers, depot capacity, grid tier, or bus pool")
    # restore the division instance
    os.environ["ROUTE_INPUTS"] = "garage_inputs_v5.json"
    import importlib
    importlib.reload(R)
    return agg


def stability(base_rec):
    """Near-optimal equipment-count ranges at F* + TAU (protocol 5.4)."""
    K = range(len(R.BUS_CLASSES))
    out = {"tau": TAU, "base_diff_cost": base_rec["differentiating_cost"]}
    targets = {
        "n_ffh": lambda h: gp.quicksum(h["x"][k] for k in K
                                       if R.BUS_CLASSES[k].ffh),
        "n_ext": lambda h: gp.quicksum(h["x"][k] for k in K
                                       if R.BUS_CLASSES[k].batt_nom > 600),
        "n_opp": lambda h: gp.quicksum(h["wch"][n, p] for n in R.SITES
                                       for p in R.CH_CLASSES if n != "depot"),
    }
    for name, expr in targets.items():
        for sense, tag in ((GRB.MINIMIZE, "min"), (GRB.MAXIMIZE, "max")):
            lbl = f"stab_{name}_{tag}"
            m = R.build_model(carbon_price_t=LAM, fix_fleet_total=True,
                              diff_objective=True)
            m.addConstr(m._total_cost <= base_rec["obj_solver"] + TAU)
            m.setObjective(expr(m._handles), sense)
            limits(m, lbl, tlim=3600, gap=0.5)
            m.optimize()
            val = m.ObjVal if m.SolCount else None
            out[lbl] = round(val, 2) if val is not None else None
            print(lbl, "->", out[lbl], flush=True)
            OUT["cases"]["stability"] = out
            dump()
    return out


if __name__ == "__main__":
    which = sys.argv[1:] or ["A", "B", "C", "D", "stability"]
    t0 = time.time()
    print("=== division counterfactuals |", os.environ["ROUTE_INPUTS"],
          "| blocks", R.N_BLOCKS, "| lam", LAM, flush=True)

    if "D" in which:
        rec, _ = solve_case("D_full_coordination")
        if rec:
            OUT["cases"]["D_full_coordination"] = rec
            dump()
    if "C" in which:
        rec, _ = solve_case("C_shared_infra_frozen_z", freeze_z=True)
        if rec:
            OUT["cases"]["C_shared_infra_frozen_z"] = rec
            dump()
    if "B" in which:
        rec, _ = solve_case("B_shared_infra_route_locked", route_lock=True)
        if rec:
            OUT["cases"]["B_shared_infra_route_locked"] = rec
            dump()
    if "A" in which:
        OUT["cases"]["A_fragmented"] = case_A()
        dump()
    if "stability" in which and "D_full_coordination" in OUT["cases"]:
        stability(OUT["cases"]["D_full_coordination"])
        dump()

    OUT["meta"] = {"minutes": round((time.time() - t0) / 60, 1),
                   "lam": LAM, "tau": TAU, "abs_gap_diff_cost": ABS_GAP,
                   "gurobi": gp.gurobi.version()}
    dump()
    print("division campaign done in", OUT["meta"]["minutes"], "min", flush=True)
