"""
Tighten the loose per-route subproblems of division case A.

Case A's reported cost is the SUM of 14 independent route optima, so its
uncertainty is the SUM of 14 optimality gaps, not one gap. The first pass left
about 72 kCAD of accumulated slack (4 routes above 1 kCAD, worst 7.5 kCAD),
which is large enough to swamp any fragmented-versus-coordinated comparison.

Unlike the division-scale cases, these subproblems are small (5-11 blocks) and
close in seconds to minutes, so the slack is cheap to remove: each loose route
is re-solved warm-started from its recorded design at a tighter absolute
tolerance. Records are replaced only when the gap actually improves, and the
case-A aggregate is then recomputed from the per-route records.

Waits for a running case A to finish before touching div_A.json.

Usage:
  ROUTE_INPUTS=garage_inputs_v5.json DIV_THREADS=16 python3 tighten_A_v6.py \
      [target_abs_gap] [tlim]
"""

import importlib
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("ROUTE_INPUTS", "garage_inputs_v5.json")

import campaign_division_v5 as D
import route52_prototype as R

OUT_FILE = os.environ.get("DIV_A_OUT", "div_A.json")
TARGET = float(sys.argv[1]) if len(sys.argv) > 1 else 250.0
TLIM = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
BASE_INPUTS = "garage_inputs_v5.json"


def wait_for_case_A():
    while True:
        p = subprocess.run(["pgrep", "-f", "campaign_division_v5.py A"],
                           capture_output=True, text=True)
        if not p.stdout.strip():
            return
        print("waiting for case A to finish...", flush=True)
        time.sleep(60)


def sub_instance(base, r):
    """Rebuild the standalone instance for one route, as case_A does."""
    brs = {k: v for k, v in base["branches"].items() if D.route_of(k) == r}
    sites = sorted({"depot"} | {v["site_west"] for v in brs.values()}
                   | {v["site_east"] for v in brs.values()})
    sub = dict(base)
    sub["branches"] = brs
    sub["sites"] = sites
    sub["instance_name"] = f"route_{r}_standalone"
    fn = f"_sub_route_{r}.json"
    path = os.path.join(os.path.dirname(os.path.abspath(R.__file__)), fn)
    json.dump(sub, open(path, "w"), indent=1)
    return fn


def seed_from(rec, mod):
    """Recorded design -> MIP start, in the reloaded module's index space."""
    name2k = {bc.name: k for k, bc in enumerate(mod.BUS_CLASSES)}
    x = {k: 0 for k in range(len(mod.BUS_CLASSES))}
    for nm, c in rec["fleet"].items():
        x[name2k[nm]] = c
    wch = {(n, p): 0 for n in mod.SITES for p in mod.CH_CLASSES}
    for key, c in rec["chargers"].items():
        n, p = key.split(":")
        if n in mod.SITES:
            wch[(n, int(p))] = c
    ygrid = {(n, j): 0 for n in mod.SITES for j in range(len(mod.GRID_TIERS))}
    for n, kw in rec.get("grid_kW", {}).items():
        if n not in mod.SITES:
            continue
        for j, g in enumerate(mod.GRID_TIERS):
            if abs(g - kw) < 1e-6:
                ygrid[(n, j)] = 1
    return x, wch, ygrid


def aggregate(per_route):
    agg = {"label": "A_fragmented", "per_route": per_route}
    tot = {k: 0.0 for k in ("total_annual_cost", "differentiating_cost",
                            "diesel_L", "co2_t")}
    counts = {k: 0 for k in ("n_buses", "n_ffh", "n_ext", "n_opp_chargers")}
    chargers, gridkw, worst, gapsum = {}, {}, 0.0, 0.0
    for r, rec in per_route.items():
        for k in tot:
            tot[k] += rec[k]
        for k in counts:
            counts[k] += rec[k]
        for kk, v in rec["chargers"].items():
            chargers[kk] = chargers.get(kk, 0) + v
        for n, v in rec.get("grid_kW", {}).items():
            gridkw[n] = gridkw.get(n, 0) + v
        worst = max(worst, rec["abs_gap"])
        gapsum += rec["abs_gap"]
    agg.update({k: round(v, 1) for k, v in tot.items()})
    agg.update(counts)
    agg["chargers"] = chargers
    agg["grid_kW"] = gridkw
    agg["worst_route_gap"] = round(worst, 1)
    # the honest uncertainty on a sum of independent optima
    agg["abs_gap"] = round(gapsum, 1)
    agg["gap_note"] = ("sum of the 14 per-route absolute gaps; case A is a "
                       "sum of independent optima, so its slack accumulates")
    agg["note"] = ("sum of 14 independent route optima; no shared terminal "
                   "chargers, depot capacity, grid tier, or bus pool")
    return agg


if __name__ == "__main__":
    wait_for_case_A()
    out = json.load(open(OUT_FILE))
    per = out["cases"]["A_fragmented"]["per_route"]
    base = json.load(open(BASE_INPUTS))
    loose = {r: rec for r, rec in per.items() if rec["abs_gap"] > TARGET}
    print(f"{len(per)} routes recorded | {len(loose)} above {TARGET:.0f} CAD "
          f"| summed gap {sum(v['abs_gap'] for v in per.values()):,.0f} CAD",
          flush=True)

    for r in sorted(loose, key=lambda r: -per[r]["abs_gap"]):
        rec = per[r]
        fn = sub_instance(base, r)
        os.environ["ROUTE_INPUTS"] = fn
        importlib.reload(R)
        m = R.build_model(carbon_price_t=D.LAM, fix_fleet_total=True,
                          diff_objective=True)
        h = m._handles
        x, wch, ygrid = seed_from(rec, R)
        for k in range(len(R.BUS_CLASSES)):
            h["x"][k].Start = x[k]
        for n in R.SITES:
            for p in R.CH_CLASSES:
                h["wch"][n, p].Start = wch[(n, p)]
                h["ysite"][n, p].Start = 1 if wch[(n, p)] > 0 else 0
            for j in range(len(R.GRID_TIERS)):
                h["ygrid"][n, j].Start = ygrid[(n, j)]
        D.limits(m, f"A_route_{r}_tight", tlim=TLIM, gap=TARGET)
        m.optimize()
        if m.SolCount == 0:
            print(f"  route {r}: no solution, keeping recorded", flush=True)
            continue
        new = D.summarize(m, f"A_route_{r}")
        if new["abs_gap"] < rec["abs_gap"]:
            print(f"  route {r}: gap {rec['abs_gap']:,.0f} -> "
                  f"{new['abs_gap']:,.0f} | diff "
                  f"{rec['differentiating_cost']/1e3:.1f}k -> "
                  f"{new['differentiating_cost']/1e3:.1f}k", flush=True)
            per[r] = new
        else:
            print(f"  route {r}: gap not improved "
                  f"({rec['abs_gap']:,.0f} -> {new['abs_gap']:,.0f}), kept",
                  flush=True)
        out["cases"]["A_fragmented"] = aggregate(per)
        json.dump(out, open(OUT_FILE, "w"), indent=1)

    out["cases"]["A_fragmented"] = aggregate(per)
    json.dump(out, open(OUT_FILE, "w"), indent=1)
    a = out["cases"]["A_fragmented"]
    print(f"\ncase A: diff {a['differentiating_cost']/1e3:,.1f} kCAD | "
          f"summed gap {a['abs_gap']:,.0f} CAD | worst route "
          f"{a['worst_route_gap']:,.0f} | FFH {a['n_ffh']}/{a['n_buses']}",
          flush=True)
