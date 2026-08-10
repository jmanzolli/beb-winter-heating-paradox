"""VSS and the wait-and-see bound under a soft heat balance.

Why the soft balance is needed. The mean-temperature design cannot be operated
in the three coldest bands, so the expected result of the expected-value
solution (EEV) is +infinity and VSS is undefined -- the paper can only say
"infeasible". Allowing cabin heat to go unmet at a declared penalty makes EEV
finite and turns the statement into a number: what the deterministic design
costs once its winters are actually priced.

  RP   value of the recourse problem   = the stochastic design
  EEV  expected value of the EV solution = mean-temperature design, first
       stage fixed, evaluated over the full scenario set
  VSS  = EEV - RP

A NOTE ON EVPI. In a classic two-stage program the scenarios are mutually
exclusive futures and the wait-and-see value is the expected cost of knowing
which one occurs. Here they are not: the weather bands all occur within the
same planning year, with weights summing to 365 days, and the agency buys one
fleet for all of them. The wait-and-see problem -- a separate optimal fleet
per band -- is therefore not implementable, and EVPI computed from it is not
the value of any information an operator could acquire. It is computed anyway
below, clearly labelled, because it bounds how much of the cost is driven by
having to serve every band with one design; it should not be reported as EVPI
without that caveat.

Run: ROUTE_INPUTS=route52_inputs_v7.json python3 evpi_vss_run.py
"""
import json
import os

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v7.json")
os.environ.setdefault("CAMP_OUT", "evpi_vss_results.json")

import gurobipy as gp

import campaign_v5 as C
import route52_prototype as R

OUT_FILE = os.environ.get("EVPI_OUT", "evpi_vss.json")
PEN = float(os.environ.get("EVPI_HEAT_PENALTY", R.SHORTFALL_PENALTY))
TLIM = int(os.environ.get("EVPI_TLIM", 1800))
SRC = os.environ.get("EVPI_SRC", "campaign_v8_results.json")

SRC_RUNS = {r["label"]: r for r in json.load(open(SRC))["runs"]
            if "error" not in r and not r.get("infeasible")}


def solve(label, fix_design=None, only_scen=None, tlim=TLIM):
    m = R.build_model(carbon_price_t=0.0, soft_heat=True, heat_penalty=PEN,
                      only_scen=only_scen)
    if fix_design:
        h = m._handles
        for k, v in fix_design["x"].items():
            m.addConstr(h["x"][int(k)] == v)
        for (n, p), v in fix_design["wch"].items():
            m.addConstr(h["wch"][n, p] == v)
        for (n, j), v in fix_design["ygrid"].items():
            m.addConstr(h["ygrid"][n, j] == v)
    m.Params.OutputFlag = 1
    m.Params.LogToConsole = 0
    m.Params.LogFile = f"logs_v5/evpi_{label}.log"
    m.Params.MIPGapAbs = C.ABS_GAP
    m.Params.TimeLimit = tlim
    m.Params.Threads = C.THREADS
    m.optimize()
    if m.SolCount == 0:
        print(f"{label} -> NO SOLUTION status {m.Status}", flush=True)
        return None
    heat = m._heat_short.getValue() if hasattr(m._heat_short, "getValue") else 0.0
    rec = {"label": label,
           "objective": round(m.ObjVal, 1),
           "bound": round(m.ObjBound, 1),
           "abs_gap": round(m.ObjVal - m.ObjBound, 1),
           "resource_cost": round(m._total_cost.getValue(), 1),
           "unmet_heat_kWh_yr": round(heat, 1),
           "penalty_cost": round(PEN * heat, 1),
           "co2_t": round(m._emis_t.getValue(), 3),
           "time_s": round(m.Runtime, 1)}
    print(f"{label} -> obj {rec['objective']:,.0f} | resource "
          f"{rec['resource_cost']:,.0f} | unmet {rec['unmet_heat_kWh_yr']:,.0f} kWh"
          f" | gap {rec['abs_gap']:,.0f} ({rec['time_s']:.0f}s)", flush=True)
    return rec


out = {"heat_penalty_CAD_per_kWh": PEN, "runs": {}}

# --- RP: the stochastic design, re-solved under the soft balance ------------
out["runs"]["RP_stochastic"] = solve("RP_stochastic")

# --- EEV: mean-temperature first stage, evaluated on the full set -----------
det = SRC_RUNS.get("det_meanT")
if det:
    out["runs"]["EEV_meantemp"] = solve("EEV_meantemp",
                                        fix_design=C.design_from_record(det))

# --- WS: a separate optimal design per band (NOT implementable) -------------
ws = {}
for w in R.SCEN:
    if w in R.HEATLESS:
        continue
    r = solve(f"WS_{w}", only_scen=w, tlim=max(600, TLIM // 3))
    if r:
        ws[w] = r
out["runs"]["WS_by_band"] = ws

rp = out["runs"].get("RP_stochastic")
eev = out["runs"].get("EEV_meantemp")
if rp and eev:
    out["VSS"] = round(eev["objective"] - rp["objective"], 1)
    out["VSS_resource_only"] = round(eev["resource_cost"] - rp["resource_cost"], 1)
    out["EEV_unmet_heat_kWh_yr"] = eev["unmet_heat_kWh_yr"]

json.dump(out, open(OUT_FILE, "w"), indent=1)
print()
if rp and eev:
    print(f"RP  {rp['objective']:,.0f}")
    print(f"EEV {eev['objective']:,.0f}  (unmet heat {eev['unmet_heat_kWh_yr']:,.0f} kWh/yr)")
    print(f"VSS {out['VSS']:,.0f} CAD/yr  "
          f"(of which {out['VSS_resource_only']:,.0f} is resource cost, "
          f"the rest the comfort penalty at {PEN:g} CAD/kWh)")
