"""Rebuild the case-A aggregate from the per-route records already on disk.

case_A() dumps its aggregate after every route but only fills in the totals
after the loop, and the v8 run crashed between the two on a hardcoded
"garage_inputs_v5.json" reload (now fixed). All fourteen route solves had
completed and their records -- including lb_solver -- survived, so the
aggregate is pure arithmetic over them: no route needs re-solving.

Reproduces exactly what case_A() accumulates.

Run: DIV_OUT=campaign_division_v8.json python repair_case_A.py
"""
import json
import os

OUT_FILE = os.environ.get("DIV_OUT", "campaign_division_v8.json")
D = json.load(open(OUT_FILE))
agg = D["cases"]["A_fragmented"]
per = agg["per_route"]
assert per, "no per-route records to aggregate"

tot = {k: 0.0 for k in ("total_annual_cost", "differentiating_cost",
                        "diesel_L", "co2_t")}
counts = {k: 0 for k in ("n_buses", "n_ffh", "n_ext", "n_opp_chargers")}
chargers, gridkw, worst_gap = {}, {}, 0.0

for r in sorted(per):
    rec = per[r]
    for k in tot:
        tot[k] += rec[k]
    for k in counts:
        counts[k] += rec[k]
    for kk, v in rec["chargers"].items():
        chargers[kk] = chargers.get(kk, 0) + v
    for n, v in rec.get("grid_kW", {}).items():
        gridkw[n] = gridkw.get(n, 0) + v
    worst_gap = max(worst_gap, rec["abs_gap"])

agg.update({k: round(v, 1) for k, v in tot.items()})
agg.update(counts)
agg["chargers"] = chargers
agg["grid_kW"] = gridkw
agg["worst_route_gap"] = worst_gap
agg["note"] = ("sum of 14 independent route optima; no shared terminal "
               "chargers, depot capacity, grid tier, or bus pool")
agg["rebuilt_from_per_route"] = True

json.dump(D, open(OUT_FILE, "w"), indent=1)

lb = sum(v["lb_solver"] for v in per.values())
print(f"{len(per)} routes | incumbent {tot['differentiating_cost']:,.1f} "
      f"| certified bound {lb:,.1f}")
print(f"FFH {counts['n_ffh']}/{counts['n_buses']} buses | worst gap {worst_gap:,.0f}")
for k, v in D["cases"].items():
    if k != "A_fragmented":
        print(f"  {k}: diff {v.get('differentiating_cost', 0):,.1f}")
