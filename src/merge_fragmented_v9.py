"""Merge the per-route fragmented solves (case A, run as parallel processes)
and re-bill the fragmented plan on one shared depot connection and meter.

The certified bound compares the sum of per-route lower bounds with the best
coordinated incumbent, under the fragmented definition in which every route
has its own depot connection and is billed on its own peak. A single Arrow
Road depot would instead have one 600 kW connection and one meter billed on
the coincident peak. This script keeps the fourteen per-route designs and
dispatches fixed, sums their depot loads per time step and scenario, and
replaces the per-route depot demand charges and depot grid upgrades with those
of one shared depot ("common basis"). The result is a re-evaluated incumbent
for the fragmented plan, not a bound.

Run: ROUTE_INPUTS=garage_inputs_v9.json python merge_fragmented_v9.py \
        <division results file to update> <per-route file> [<per-route file> ...]
"""
import json
import sys

import route52_prototype as R

target, parts = sys.argv[1], sys.argv[2:]
per = {}
for fn in parts:
    a = json.load(open(fn))["cases"]["A_fragmented"]
    per.update(a["per_route"])

agg = {"label": "A_fragmented", "per_route": per}
for k in ("total_annual_cost", "differentiating_cost", "diesel_L", "co2_t"):
    agg[k] = round(sum(r[k] for r in per.values()), 1)
for k in ("n_buses", "n_ffh", "n_ext", "n_opp_chargers"):
    agg[k] = sum(r[k] for r in per.values())
ch, gk = {}, {}
for r in per.values():
    for kk, v in r["chargers"].items():
        ch[kk] = ch.get(kk, 0) + v
    for n, v in r["grid_kW"].items():
        gk[n] = gk.get(n, 0) + v
agg["chargers"], agg["grid_kW"] = ch, gk
agg["worst_route_gap"] = max(r["abs_gap"] for r in per.values())
agg["lb_sum"] = round(sum(r["lb_solver"] for r in per.values()), 1)
agg["sum_route_depot_peaks_kW"] = round(sum(r["peak_depot_kW"] for r in per.values()), 1)
agg["note"] = ("sum of 14 independent route optima; each route planned with its "
               "own depot connection and billed on its own peak")

# ---- common basis: one depot connection, one meter on the coincident peak
scen = list(next(iter(per.values()))["depot_kW"])
nT = len(next(iter(per.values()))["depot_kW"][scen[0]])
coinc = {w: [sum(r["depot_kW"][w][t] for r in per.values()) for t in range(nT)]
         for w in scen}
peak = {"win": max(max(coinc[w]) for w in scen if w not in R.HEATLESS),
        "off": max(max(coinc[w]) for w in scen if w in R.HEATLESS)}
shared_dem = R.demand_rate("depot") * (R.WINTER_MONTHS * peak["win"]
                                       + R.OFFSEASON_MONTHS * peak["off"])
need = max(peak.values()) - R.GRID_EXISTING["depot"]
tier = None
if need > 0:
    fits = [j for j, g in enumerate(R.GRID_TIERS) if g >= need]
    tier = fits[0] if fits else None
shared_grid = R.CRF_GRID * R.GRID_TIER_COST[tier] if tier is not None else 0.0
sep_dem = sum(r["depot_demand_cost"] for r in per.values())
sep_grid = sum(r["depot_grid_cost"] for r in per.values())
cb = agg["differentiating_cost"] - sep_dem - sep_grid + shared_dem + shared_grid
agg["common_basis"] = {
    "coincident_peak_kW": {k: round(v, 1) for k, v in peak.items()},
    "shared_grid_tier_kW": R.GRID_TIERS[tier] if tier is not None else 0,
    "shared_grid_tier_feasible": tier is not None or need <= 0,
    "separate_depot_demand_cost": round(sep_dem, 1),
    "separate_depot_grid_cost": round(sep_grid, 1),
    "shared_depot_demand_cost": round(shared_dem, 1),
    "shared_depot_grid_cost": round(shared_grid, 1),
    "differentiating_cost": round(cb, 1),
    "note": ("fragmented designs and dispatch fixed; depot demand charges and "
             "depot grid upgrade re-billed for one shared connection and meter; "
             "a re-evaluated incumbent, not a bound"),
}
out = json.load(open(target))
out["cases"]["A_fragmented"] = agg
json.dump(out, open(target, "w"), indent=1)
print(json.dumps({k: agg[k] for k in ("differentiating_cost", "lb_sum", "n_ffh",
                                      "sum_route_depot_peaks_kW")}, indent=1))
print(json.dumps(agg["common_basis"], indent=1))
