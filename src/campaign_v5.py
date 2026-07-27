"""
Route 52 v5 revision campaign (T-ITS revision protocol, Sections 3, 5.1-5.2).

Every run: archived Gurobi log (logs_v5/<label>.log), structured record with
incumbent, lower bound, absolute and relative gap, runtime, status, cost
decomposition, fleet, infrastructure, and per-scenario operations.

Emissions-cap points use the LEXICOGRAPHIC two-phase method (replaces the
augmented eps-constraint of the previous draft):
  phase 1: min total cost s.t. emissions <= eps       (abs gap <= ABS_GAP)
  phase 2: fix total cost <= incumbent + LEX_TOL, min emissions.

F1 convention: F1 = resource cost (capex + demand charges + energy + diesel
+ FFH O&M), excluding carbon payments. The solver objective at carbon price
lambda equals F1 + lambda*F2; records store both.

Usage: ROUTE_INPUTS=route52_inputs_v5.json python3 campaign_v5.py
"""

import json
import os
import time

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")

import gurobipy as gp
from gurobipy import GRB

import route52_prototype as R

ABS_GAP = 1000.0
LEX_TOL = 500.0
TLIM = 3600
TLIM_HARD = 7200
LOGDIR = "logs_v5"
os.makedirs(LOGDIR, exist_ok=True)

# memory safety (16 GB laptop): a hard branch-and-bound tree caused a Gurobi
# out-of-memory abort in the first campaign pass. Spill the tree to disk and
# cap threads/memory so a hard run degrades to a time/memory limit with an
# incumbent instead of killing the process.
import socket
_HOST = socket.gethostname()
THREADS = int(os.environ.get("CAMP_THREADS", 6))
NODEFILE_START_GB = float(os.environ.get("CAMP_NODEFILE_GB", 1.0))
MEM_LIMIT_GB = float(os.environ.get("CAMP_MEM_GB", 11.0))
NODEFILE_DIR = "gurobi_nodefiles"
os.makedirs(NODEFILE_DIR, exist_ok=True)

# Env-overridable so independent subsets can run as concurrent processes on a
# many-core host, each writing its own shard (merge with merge_campaign.py).
OUT_FILE = os.environ.get("CAMP_OUT", "campaign_v5_results.json")
OUT = {"runs": [], "meta": {
    "inputs": os.environ["ROUTE_INPUTS"],
    "abs_gap": ABS_GAP, "lex_tol": LEX_TOL,
    "scen_days": {w: R.SCEN[w][1] for w in R.SCEN},
    "ffh_rated_kw": R.P_FFH_RATED, "el_heater_rated_kw": R.P_ELH_RATED,
    "reserve_kwh": R.RESERVE_RETURN,
    "formulation": "v6 (C1 heater-bounded preconditioning, C2 chi retention, "
                   "C3 single plug per bus, C4 FFH-free procurement)",
    "precond_tau_h": R.PRECOND_TAU_H,
    "precond_max_kwh": R.PRECOND_MAX_KWH,
    "gurobi": gp.gurobi.version(), "threads": "all (default)",
}}


# resume: reload any runs already certified in a previous pass so an
# interrupted campaign continues instead of recomputing
DONE = {}
if os.path.exists(OUT_FILE):
    _prev = json.load(open(OUT_FILE))
    OUT["runs"] = _prev.get("runs", [])
    for _k in ("ops_metrics_policy", "frontier_labels", "breakpoint_prices",
               "det_feasible_full", "n_minus_1_feasible"):
        if _k in _prev:
            OUT[_k] = _prev[_k]
    DONE = {r["label"]: r for r in OUT["runs"]}
    print(f"resume: {len(DONE)} runs already recorded", flush=True)


def _dump():
    json.dump(OUT, open(OUT_FILE, "w"), indent=1)


def _apply_limits(m, tlim, abs_gap, label):
    # OutputFlag=0 suppresses the log FILE as well as the console, which left
    # the first-pass archives empty. Keep file logging on, console off.
    m.Params.OutputFlag = 1
    m.Params.LogToConsole = 0
    m.Params.LogFile = f"{LOGDIR}/{label}.log"
    m.Params.MIPGapAbs = abs_gap
    m.Params.TimeLimit = tlim
    m.Params.Threads = THREADS
    m.Params.NodefileStart = NODEFILE_START_GB
    m.Params.NodefileDir = NODEFILE_DIR
    m.Params.SoftMemLimit = MEM_LIMIT_GB


def design_from_record(rec):
    """Reconstruct a first-stage design dict from a stored run record."""
    name2k = {bc.name: k for k, bc in enumerate(R.BUS_CLASSES)}
    x = {k: 0 for k in range(len(R.BUS_CLASSES))}
    for name, cnt in rec["fleet"].items():
        x[name2k[name]] = cnt
    wch = {(n, p): 0 for n in R.SITES for p in R.CH_CLASSES}
    for key, cnt in rec["chargers"].items():
        n, p = key.split(":")
        wch[(n, int(p))] = cnt
    ysite = {k: (1 if v > 0 else 0) for k, v in wch.items()}
    ygrid = {(n, j): 0 for n in R.SITES for j in range(len(R.GRID_TIERS))}
    for n, kw in rec.get("grid_kW", {}).items():
        for j, g in enumerate(R.GRID_TIERS):
            if abs(g - kw) < 1e-6:
                ygrid[(n, j)] = 1
    return {"x": x, "wch": wch, "ysite": ysite, "ygrid": ygrid}


def cost_parts(m, lam):
    h = m._handles
    K = range(len(R.BUS_CLASSES))
    J = range(len(R.GRID_TIERS))
    bus = R.CRF_BUS * sum(R.BUS_CLASSES[k].cost * h["x"][k].X for k in K)
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
    co2 = dL * R.CO2_PER_L / 1000.0
    return {"bus_capital": bus, "charger_site_capital": ch, "grid_capital": grid,
            "demand_charges": dem, "electricity": en, "ffh_om": om,
            "diesel_cost": R.DIESEL_PRICE * dL, "carbon_cost": lam * co2,
            "diesel_L": dL, "co2_t": co2,
            "F1": bus + ch + grid + dem + en + om + R.DIESEL_PRICE * dL}


def record(m, label, lam, eps, phase2=None, extra=None):
    h = m._handles
    K = range(len(R.BUS_CLASSES))
    cp = cost_parts(m, lam)
    rel = abs(m.ObjVal - m.ObjBound) / max(1.0, abs(m.ObjVal))
    r = {"label": label, "lam": lam, "eps": eps,
         "obj": round(m.ObjVal + m._const_addback, 1),
         "lb": round(m.ObjBound + m._const_addback, 1),
         "abs_gap": round(m.ObjVal - m.ObjBound, 1),
         "rel_gap": round(rel, 6), "time_s": round(m.Runtime, 1),
         "status": int(m.Status), "phase2": phase2,
         # protocol Section 8 requires hardware per experiment; runs may be
         # split across machines, so each record carries its own host
         "host": _HOST, "threads": THREADS,
         "F1": round(cp["F1"], 1), "co2_t": round(cp["co2_t"], 3),
         "diesel_L": round(cp["diesel_L"], 1),
         "diesel_by_scen": {w: round(m._scen[w]["D"].X, 2) for w in R.SCEN},
         # per-scenario operation, so Table IV is generated from the archive
         # instead of being recovered by re-solving (protocol Section 6)
         "scen_ops": {w: {
             "T": R.SCEN[w][0], "days": R.SCEN[w][1],
             "q_el_kWh": round(sum(v.X for v in m._scen[w]["qel"].values()), 1),
             "q_ffh_kWh": round(sum(v.X for v in m._scen[w]["qff"].values()), 1),
             "diesel_L": round(m._scen[w]["D"].X, 2),
             "precond_kWh": round(sum(R.DT * v.X
                                      for v in m._scen[w]["ppre"].values()), 1),
             "electricity_cost": round(
                 m._scen[w]["energy_cost"].getValue(), 2),
         } for w in R.SCEN},
         "cost_parts": {k: round(v, 1) for k, v in cp.items()},
         "n_ffh": int(round(sum(h["x"][k].X for k in K if R.BUS_CLASSES[k].ffh))),
         "n_ext": int(round(sum(h["x"][k].X for k in K
                                if R.BUS_CLASSES[k].batt_nom > 600))),
         "fleet": {R.BUS_CLASSES[k].name: int(round(h["x"][k].X))
                   for k in K if h["x"][k].X > 0.5},
         "chargers": {f"{n}:{p}": int(round(h["wch"][n, p].X))
                      for n in R.SITES for p in R.CH_CLASSES
                      if h["wch"][n, p].X > 0.5},
         "grid_kW": {n: round(h["g_add"][n].getValue(), 0)
                     for n in R.SITES if h["g_add"][n].getValue() > 1},
         # C5: preconditioning diagnostics, so a heater-rating defect is
         # detectable from the archive without re-solving
         "precond": {
             "peak_kW": round(max(
                 (v.X for w in R.SCEN for v in m._scen[w]["ppre"].values()),
                 default=0.0), 2),
             "annual_kWh": round(sum(
                 R.SCEN[w][1] * R.DT * v.X
                 for w in R.SCEN for v in m._scen[w]["ppre"].values()), 1),
             "tau_h": R.PRECOND_TAU_H},
         "rho_kW": {f"{n}:{l}": round(h["rho"][n, l].X, 1)
                    for n in R.SITES for l in ("win", "off")
                    if h["rho"][n, l].X > 1}}
    if extra:
        r.update(extra)
    return r


def solve(label, eps=None, lam=100.0, mods=None, unmods=None, tlim=TLIM,
          abs_gap=ABS_GAP, lexicographic=False, fix_design=None,
          freeze_z=False, spare=0.0, force=False, mip_start=None, **bm_kwargs):
    if label in DONE and not force:
        print(f"{label} -> skip (already recorded)", flush=True)
        return DONE[label], None
    if mods:
        mods()
    try:
        m = R.build_model(eps_cap_t=eps, carbon_price_t=lam,
                          spare_ratio=spare, **bm_kwargs)
        h = m._handles
        if fix_design:
            for k in range(len(R.BUS_CLASSES)):
                m.addConstr(h["x"][k] == fix_design["x"][k])
            for n in R.SITES:
                for p in R.CH_CLASSES:
                    m.addConstr(h["wch"][n, p] == fix_design["wch"][(n, p)])
                    m.addConstr(h["ysite"][n, p] == fix_design["ysite"][(n, p)])
                for j in range(len(R.GRID_TIERS)):
                    m.addConstr(h["ygrid"][n, j] == fix_design["ygrid"][(n, j)])
        if mip_start:
            for k in range(len(R.BUS_CLASSES)):
                h["x"][k].Start = mip_start["x"][k]
            for n in R.SITES:
                for p in R.CH_CLASSES:
                    h["wch"][n, p].Start = mip_start["wch"][(n, p)]
                    h["ysite"][n, p].Start = mip_start["ysite"][(n, p)]
                for j in range(len(R.GRID_TIERS)):
                    h["ygrid"][n, j].Start = mip_start["ygrid"][(n, j)]
        if freeze_z:
            W = list(R.SCEN.keys())
            z0 = m._scen[W[0]]["z"]
            for w in W[1:]:
                zw = m._scen[w]["z"]
                for key in z0:
                    m.addConstr(zw[key] == z0[key])
        _apply_limits(m, tlim, abs_gap, label)
        try:
            m.optimize()
        except gp.GurobiError as e:
            print(label, "-> GurobiError:", e, flush=True)
            OUT["runs"].append({"label": label, "error": str(e),
                                "lam": lam, "eps": eps})
            _dump()
            return None, None
        if m.SolCount == 0:
            print(label, "-> NO SOLUTION status", m.Status, flush=True)
            OUT["runs"].append({"label": label, "status": int(m.Status),
                                "infeasible": True, "lam": lam, "eps": eps})
            _dump()
            return None, None
        phase2 = None
        if lexicographic and eps is not None:
            f1_inc, f1_lb, t1 = m.ObjVal, m.ObjBound, m.Runtime
            co2_p1 = m._emis_t.getValue()
            m.addConstr(m._total_cost <= f1_inc + LEX_TOL, name="lex_cost_cap")
            m.setObjective(m._emis_t, GRB.MINIMIZE)
            m.Params.LogFile = f"{LOGDIR}/{label}_ph2.log"
            m.Params.MIPGapAbs = 0.05          # tonnes
            m.Params.TimeLimit = 1800
            try:
                m.optimize()
            except gp.GurobiError as e:
                print(label, "-> phase-2 GurobiError:", e, flush=True)
            phase2 = {"cost_incumbent_ph1": round(f1_inc, 1),
                      "cost_lb_ph1": round(f1_lb, 1),
                      "time_ph1": round(t1, 1),
                      "co2_ph1": round(co2_p1, 3),
                      "co2_ph2": round(m._emis_t.getValue(), 3),
                      "lex_tol": LEX_TOL}
            # reporting bounds refer to phase-1 cost certification
            rec = record(m, label, lam, eps, phase2=phase2)
            rec["obj"] = round(f1_inc + m._const_addback, 1)
            rec["lb"] = round(f1_lb + m._const_addback, 1)
            rec["abs_gap"] = round(f1_inc - f1_lb, 1)
            rec["rel_gap"] = round(abs(f1_inc - f1_lb) / max(1.0, abs(f1_inc)), 6)
            rec["obj_final_cost"] = round(m._total_cost.getValue()
                                          + m._const_addback, 1)
        else:
            rec = record(m, label, lam, eps, phase2=phase2)
        OUT["runs"].append(rec)
        _dump()
        print(label, "-> obj", rec["obj"], "gap", rec["abs_gap"],
              "ffh", rec["n_ffh"], "co2", rec["co2_t"],
              f"({rec['time_s']}s)", flush=True)
        return rec, m
    finally:
        if unmods:
            unmods()


def design_of(m):
    h = m._handles
    return {"x": {k: round(h["x"][k].X) for k in range(len(R.BUS_CLASSES))},
            "wch": {(n, p): round(h["wch"][n, p].X)
                    for n in R.SITES for p in R.CH_CLASSES},
            "ysite": {(n, p): round(h["ysite"][n, p].X)
                      for n in R.SITES for p in R.CH_CLASSES},
            "ygrid": {(n, j): round(h["ygrid"][n, j].X)
                      for n in R.SITES for j in range(len(R.GRID_TIERS))}}


def ops_metrics(m):
    out = {}
    K = range(len(R.BUS_CLASSES))
    zmaps = {}
    for w in R.SCEN:
        s = m._scen[w]
        margins = []
        for b in range(R.N_BLOCKS):
            capw = R.DERATE[w][0] * sum(R.BUS_CLASSES[k].batt_nom * s["z"][b, k].X
                                        for k in K)
            nt = len(R.BLOCKS[b].trips)
            mn = min(s["Earr"][b, i].X - R.S_LO * capw for i in range(nt))
            margins.append(mn)
        plug_h = (sum(v.X for v in s["u"].values())
                  + sum(v.X for v in s["upre"].values())) * R.DT
        zmaps[w] = {b: max(K, key=lambda k: s["z"][b, k].X)
                    for b in range(R.N_BLOCKS)}
        out[w] = {"min_reserve_kWh": round(min(margins), 1),
                  "p5_reserve_kWh": round(sorted(margins)[max(0, len(margins)//20)], 1),
                  "plug_hours": round(plug_h, 1)}
    base = zmaps[list(R.SCEN)[0]]
    for w in R.SCEN:
        out[w]["reassigned_vs_first"] = sum(1 for b in base
                                            if zmaps[w][b] != base[b])
    return out


# ---------------- mods helpers (restore-safe) ----------------
def set_om(v):
    def f(): R.FFH_ANNUAL_OM = v
    def g(): R.FFH_ANNUAL_OM = 1000.0
    return f, g

_TIER0 = list(R.GRID_TIER_COST)
def set_grid(gc):
    def f(): R.GRID_TIER_COST[:] = [gc * g_ for g_ in R.GRID_TIERS]
    def g(): R.GRID_TIER_COST[:] = _TIER0
    return f, g

_COST0 = [bc.cost for bc in R.BUS_CLASSES]
def set_batt(bp):
    def f():
        for bc in R.BUS_CLASSES:
            bc.cost = R.BUS_BASE + (118.0 * bp if bc.batt_nom > 600 else 0.0)
    def g():
        for bc, c0 in zip(R.BUS_CLASSES, _COST0):
            bc.cost = c0
    return f, g

def set_reserve(v):
    def f(): R.RESERVE_RETURN = v
    def g(): R.RESERVE_RETURN = 10.0
    return f, g

def set_tau(v):
    """C2 sensitivity on the preconditioning thermal-retention constant."""
    def f(): R.PRECOND_TAU_H = v
    def g(): R.PRECOND_TAU_H = 0.5
    return f, g

def set_ffh_capex(v):
    """Installed capital cost of the fuel-fired heater itself.

    The base instance prices an FFH only through its annual O&M: the FFH and
    electric-heating-only variants of a bus class carry the SAME purchase
    price, so the model can equip a bus with a burner at zero capital. That
    assumption works in favour of the headline result (every bus FFH-equipped
    at the economic optimum), so it has to be stress-tested rather than left
    implicit. v is the installed cost per heater, annualized at CRF_BUS.
    """
    def f():
        for bc in R.BUS_CLASSES:
            if bc.ffh:
                bc.cost += v
    def g():
        for bc, c0 in zip(R.BUS_CLASSES, _COST0):
            bc.cost = c0
    return f, g

_DER0 = dict(R.DERATE)
def set_derate(cap_slope, acc_slope):
    def f():
        for w in R.SCEN:
            T = R.SCEN[w][0]
            cap = max(1.0 - max(0.0, -T) * cap_slope, 0.85)
            acc = max(1.0 - max(0.0, -T) * acc_slope, 0.75)
            R.DERATE[w] = (cap, acc)
    def g():
        R.DERATE.update(_DER0)
    return f, g

_SCEN0 = dict(R.SCEN)
def set_deterministic():
    # days-weighted winter mean + off-season kept; used for the deterministic
    # benchmark design only
    Tbar = sum(R.SCEN[w][0] * R.SCEN[w][1] for w in R.SCEN
               if w not in R.HEATLESS) / sum(
        R.SCEN[w][1] for w in R.SCEN if w not in R.HEATLESS)
    def f():
        off = {w: R.SCEN[w] for w in R.SCEN if w in R.HEATLESS}
        R.SCEN.clear()
        R.SCEN["winteravg"] = (round(Tbar, 1), 151)
        R.SCEN.update(off)
        R.DERATE["winteravg"] = R._derates(Tbar)
    def g():
        R.SCEN.clear()
        R.SCEN.update(_SCEN0)
        R.DERATE.update(_DER0)
    return f, g


if __name__ == "__main__":
    t0 = time.time()
    print("=== v5 campaign |", os.environ["ROUTE_INPUTS"],
          "| days:", sum(R.SCEN[w][1] for w in R.SCEN), flush=True)

    # A. baselines
    econ, m0 = solve("econ_lam0", lam=0.0)
    pol, m100 = solve("policy_lam100", lam=100.0)
    d100 = design_of(m100) if m100 is not None else design_from_record(pol)
    if "ops_metrics_policy" not in OUT:
        # resumed run: recover the operating point by re-solving the recourse
        # on the recorded design (fast; first stage pinned)
        _, m100 = solve("policy_lam100_ops", lam=100.0, fix_design=d100,
                        tlim=900, force=True)
        OUT["ops_metrics_policy"] = ops_metrics(m100)
    _dump()

    # B. lexicographic eps frontier (coarse; refinement in a second pass)
    co2max = econ["co2_t"]
    frontier = []
    prev = None
    for frac in (1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.0):
        rec, mm = solve(f"eps_{frac:.2f}", eps=co2max * frac, lam=0.0,
                        lexicographic=True, tlim=TLIM_HARD)
        if rec:
            frontier.append(rec)
    OUT["frontier_labels"] = [r["label"] for r in frontier]
    _dump()

    # C. carbon-price sweep + breakpoint verification
    for lamv in (200, 500, 1000, 2000, 3500, 5000, 10000):
        solve(f"lam_{lamv}", lam=float(lamv),
              tlim=TLIM_HARD if lamv in (3500, 10000) else TLIM)
    fr = sorted(frontier, key=lambda r: -r["co2_t"])
    bps = []
    for a, b in zip(fr, fr[1:]):
        dc, de = b["F1"] - a["F1"], a["co2_t"] - b["co2_t"]
        if de > 1e-3 and dc > 0:
            bps.append(round(dc / de, 0))
    OUT["breakpoint_prices"] = sorted(set(bps))
    for lamv in sorted(set(bps))[:3]:
        solve(f"bp_lam_{int(lamv)}", lam=float(lamv), tlim=TLIM)
    _dump()

    # D. deterministic mean-temperature benchmark + full-scenario test
    f, g = set_deterministic()
    det, mdet = solve("det_meanT", lam=100.0, mods=f, unmods=None)
    ddet = (design_of(mdet) if mdet is not None
            else (design_from_record(det) if det else None))
    g()
    if ddet:
        rec, _ = solve("det_design_full_test", lam=100.0, fix_design=ddet)
        OUT["det_feasible_full"] = rec is not None
    _dump()

    # E. frozen block-class assignment
    solve("frozen_z", lam=100.0, freeze_z=True)

    # F. N-1 depot charger on fixed policy design
    dm = {k: dict(v) if isinstance(v, dict) else v for k, v in d100.items()}
    for (n, p), v in list(dm["wch"].items()):
        if n == "depot" and v > 0:
            dm["wch"][(n, p)] = v - 1
            break
    rec, _ = solve("n_minus_1", lam=100.0, fix_design=dm)
    OUT["n_minus_1_feasible"] = rec is not None
    _dump()

    # G. sensitivities
    for v in (500.0, 2000.0):
        f, g = set_om(v); solve(f"ffh_om_{int(v)}", mods=f, unmods=g)
    for gc in (100.0, 300.0):
        f, g = set_grid(gc); solve(f"grid_{int(gc)}", mods=f, unmods=g)
    for bp in (100.0, 50.0):
        f, g = set_batt(bp); solve(f"batt_{int(bp)}", mods=f, unmods=g)
    for tag, cs, as_ in (("derate_mild", 0.002, 0.004),
                         ("derate_harsh", 0.006, 0.012)):
        f, g = set_derate(cs, as_); solve(tag, mods=f, unmods=g)
    for rv in (25.0, 50.0):
        f, g = set_reserve(rv); solve(f"reserve_{int(rv)}", mods=f, unmods=g)
    # spare ratio scales purchased buses almost mechanically against a fixed
    # block count, so one representative level is reported instead of three
    for sp in (0.15,):
        solve(f"spare_{int(sp*100)}", lam=100.0, spare=sp)
    # C2: preconditioning retention sensitivity (tau = 0.5 h in the base case)
    for tv in (0.25, 1.0):
        f, g = set_tau(tv); solve(f"precond_tau_{tv}", mods=f, unmods=g)
    # FFH installed capital: the base instance gives the burner away for free
    for fc in (5_000.0, 15_000.0):
        f, g = set_ffh_capex(fc)
        solve(f"ffh_capex_{int(fc)}", mods=f, unmods=g)

    # NOTE: the FFH-free PROCUREMENT case is not run. It is redundant here:
    # the FFH and electric-heating-only variants of each class carry the same
    # purchase price, so under a zero emissions cap an FFH bus is weakly
    # dominated (equal capital, extra O&M, no usable heat) and eps_0.00
    # already procures none -- its fleet is 13 std + 5 ext electric-only.
    # The distinction between FFH-free operation and FFH-free procurement is
    # therefore empty at these cost assumptions, and is reported as such.

    # H. refinement pass: frontier points above the 1 kCAD declared tolerance
    # are re-solved with a warm start and a longer limit (protocol 5.2). Any
    # point that still misses the tolerance is reported with its true gap.
    recs = {r["label"]: r for r in OUT["runs"]}
    loose = [lb for lb in OUT.get("frontier_labels", [])
             if recs.get(lb, {}).get("abs_gap", 0) > ABS_GAP]
    print("refinement targets:", loose, flush=True)
    for lb in loose:
        r0 = recs[lb]
        solve(lb, eps=r0["eps"], lam=0.0, lexicographic=True,
              tlim=TLIM_HARD, force=True, mip_start=design_from_record(r0))
    # H2. relaxation monotonicity: the unconstrained baseline must not cost
    # more than any capped run. If a capped run found a cheaper design, the
    # baseline incumbent is loose and every increment measured against it is
    # overstated, so re-solve it warm-started from the best design found.
    recs = {r["label"]: r for r in OUT["runs"]}
    b0 = recs.get("econ_lam0")
    if b0:
        import re as _re
        _cmp = _re.compile(r"^(eps_|lam_|bp_lam_|policy_lam)")
        cheaper = [r for r in OUT["runs"] if _cmp.match(r["label"])
                   and r.get("F1", 9e18) < b0["F1"] - 1.0]
        if cheaper:
            best = min(cheaper, key=lambda r: r["F1"])
            print(f"baseline dominated by {best['label']} "
                  f"({b0['F1']:.1f} -> {best['F1']:.1f}); re-solving",
                  flush=True)
            solve("econ_lam0", lam=0.0, tlim=TLIM_HARD, force=True,
                  mip_start=design_from_record(best))

    # keep, per label, the record with the tightest certified gap
    best = {}
    for r in OUT["runs"]:
        lb = r["label"]
        if lb not in best or r.get("abs_gap", 9e9) < best[lb].get("abs_gap", 9e9):
            best[lb] = r
    seen, dedup = set(), []
    for r in OUT["runs"]:
        if r["label"] in seen:
            continue
        seen.add(r["label"])
        dedup.append(best[r["label"]])
    OUT["runs"] = dedup
    _dump()

    OUT["meta"]["total_minutes"] = round((time.time() - t0) / 60, 1)
    _dump()
    print("campaign v5 done in", OUT["meta"]["total_minutes"], "min", flush=True)
