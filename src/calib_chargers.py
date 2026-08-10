"""Which depot charging configuration reproduces the observed Route 52 diesel?

The cost-optimal v8 design installs three 300 kW depot chargers and burns
7,680 L/yr, 25% below the 10,305 L the corridor actually burned. The gap is
not necessarily a model error: the optimizer is free to install more depot
charging than the corridor operates, and it spends that power displacing
burner heat. The real configuration is not documented anywhere in our inputs,
so rather than assume one, this sweep inverts the question -- it holds the
fleet at the observed composition (18 FFH-equipped standard-battery buses,
no opportunity charging) and asks which depot configuration the observed
fuel use implies.

Every run is a fixed-design recourse solve: the first stage is pinned and
only dispatch is optimized, so each takes seconds.

Run: ROUTE_INPUTS=route52_inputs_v7.json python3 calib_chargers.py
"""
import json
import os

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v7.json")
os.environ.setdefault("CAMP_OUT", "calib_chargers_results.json")
os.environ.setdefault("CAMP_THREADS", "6")

import campaign_v5 as C
import route52_prototype as R

OBSERVED_L = 10305.0
OUT_FILE = os.environ.get("CALIB_OUT", "calib_chargers.json")

STD_FFH = next(k for k, b in enumerate(R.BUS_CLASSES) if b.name == "NF-std-FFH")


def design(n_plugs, rating, grid_kw):
    """18 FFH buses, n_plugs x rating at the depot, no terminal charging."""
    x = {k: 0 for k in range(len(R.BUS_CLASSES))}
    x[STD_FFH] = 18
    wch = {(n, p): 0 for n in R.SITES for p in R.CH_CLASSES}
    wch[("depot", rating)] = n_plugs
    ysite = {k: (1 if v > 0 else 0) for k, v in wch.items()}
    ygrid = {(n, j): 0 for n in R.SITES for j in range(len(R.GRID_TIERS))}
    if grid_kw:
        j = R.GRID_TIERS.index(grid_kw)
        ygrid[("depot", j)] = 1
    return {"x": x, "wch": wch, "ysite": ysite, "ygrid": ygrid}


# Sweep plug count at each rating. The depot connection is 600 kW before any
# upgrade, so the 250 kW tier is added only where installed power needs it --
# a configuration is not penalised for an upgrade it would not have bought.
CASES = []
for rating in (100, 150, 300):
    for n in (2, 3, 4, 6, 8, 10, 12):
        installed = n * rating
        if installed > 1600:
            continue
        grid = 0.0 if installed <= 600 else 250.0
        CASES.append((n, rating, grid))

rows = []
for n, rating, grid in CASES:
    label = f"calib_{n}x{rating}"
    rec, _ = C.solve(label, lam=0.0, tlim=600, force=True,
                     fix_design=design(n, rating, grid))
    if rec is None:
        rows.append({"n": n, "kW": rating, "installed_kW": n * rating,
                     "grid_kW": grid, "feasible": False})
        print(f"{n:2d}x{rating:<3d} -> INFEASIBLE", flush=True)
        continue
    rows.append({"n": n, "kW": rating, "installed_kW": n * rating,
                 "grid_kW": grid, "feasible": True,
                 "diesel_L": rec["diesel_L"], "co2_t": rec["co2_t"],
                 "F1": rec["F1"]})
    print(f"{n:2d}x{rating:<3d} ({n*rating:5.0f} kW) -> {rec['diesel_L']:8.0f} L "
          f"({100*(rec['diesel_L']-OBSERVED_L)/OBSERVED_L:+6.1f}% vs observed) "
          f"F1 {rec['F1']/1e3:,.1f}", flush=True)

feas = [r for r in rows if r["feasible"]]
best = min(feas, key=lambda r: abs(r["diesel_L"] - OBSERVED_L)) if feas else None
json.dump({"observed_L": OBSERVED_L, "cases": rows, "closest": best},
          open(OUT_FILE, "w"), indent=1)
print()
if best:
    print(f"closest to observed: {best['n']}x{best['kW']} "
          f"({best['installed_kW']} kW) at {best['diesel_L']:,.0f} L, "
          f"{100*(best['diesel_L']-OBSERVED_L)/OBSERVED_L:+.1f}%")
