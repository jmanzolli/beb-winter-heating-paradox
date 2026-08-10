"""Adapt a v8 campaign archive to the schema ieee_figures.py expects.

ieee_figures.py still reads the v4-era layout -- top-level "frontier",
"lambda_sweep", "breakpoint_verification" and "sensitivity" lists, and a run
labelled "policy_lambda100" -- while the campaign has written a flat "runs"
list under v5-style labels since v5. The four supplementary figures it draws
(fig:trans, fig:envelope, fig:opsm, fig:supp-sens) were therefore never
regenerated after v5 and still showed superseded numbers.

Rather than touch the plotting code, which carries the approved visual design,
this writes an adapter file in the old shape. All values are references to the
same records; nothing is recomputed.

Run: python3 v8_to_figschema.py            (writes fig_schema_v8.json)
Then: FIG_CAMPAIGN=fig_schema_v8.json FIG_GARAGE=fig_garage_v8.json \
      ROUTE_INPUTS=route52_inputs_v7.json python3 ieee_figures.py
"""
import json
import os
import re

SRC = os.environ.get("ADAPT_RES", "campaign_v8_results.json")
DIV = os.environ.get("ADAPT_DIV", "campaign_division_v8.json")
OUT = os.environ.get("ADAPT_OUT", "fig_schema_v8.json")
OUT_G = os.environ.get("ADAPT_OUT_DIV", "fig_garage_v8.json")

D = json.load(open(SRC))
runs = [r for r in D["runs"] if "error" not in r and not r.get("infeasible")]
by = {r["label"]: r for r in runs}

frontier = [by[l] for l in D.get("frontier_labels", []) if l in by]
lsweep = sorted((r for r in runs if re.fullmatch(r"lam_\d+", r["label"])),
                key=lambda r: r["lam"])
bpver = sorted((r for r in runs if r["label"].startswith("bp_lam_")),
               key=lambda r: r["lam"])
SENS = re.compile(r"^(ffh_om_|ffh_capex_|grid_|batt_|derate_|reserve_|"
                  r"spare_|precond_tau_|frozen_z|n_minus_1)")
sens = [r for r in runs if SENS.match(r["label"])]

out = dict(D)
out["frontier"] = frontier
out["lambda_sweep"] = lsweep
out["breakpoint_verification"] = bpver
out["sensitivity"] = sens
# the plotting code keys the reference design off the old label
if "policy_lam100" in by:
    ref = dict(by["policy_lam100"])
    ref["label"] = "policy_lambda100"
    out["runs"] = runs + [ref]
# ops metric keys were renamed between the two eras; map them back
_OPSMAP = {"min_reserve_kWh": "min_reserve_kWh_min",
           "p5_reserve_kWh": "min_reserve_kWh_p5",
           "plug_hours": "plug_hours_used",
           "reassigned_vs_first": "reassigned_blocks_vs_mildest"}
for _key in ("ops_metrics_policy", "ops_metrics_econ"):
    om = out.get(_key)
    if not om:
        continue
    out[_key] = {w: {**v, **{new: v[old] for old, new in _OPSMAP.items()
                             if old in v}}
                 for w, v in om.items()}

json.dump(out, open(OUT, "w"), indent=1)

# division: a list of records under the labels the figure code expects
cases = json.load(open(DIV))["cases"] if os.path.exists(DIV) else {}
best = min((k for k in cases
            if k != "A_fragmented" and cases[k].get("differentiating_cost")),
           key=lambda k: cases[k]["differentiating_cost"], default=None)
g = []
if "A_fragmented" in cases:
    g.append(dict(cases["A_fragmented"], label="garage_lam0"))
if best:
    g.append(dict(cases[best], label="garage_lam100"))
json.dump(g, open(OUT_G, "w"), indent=1)

print(f"{OUT}: frontier {len(frontier)} | lambda {len(lsweep)} | "
      f"breakpoints {len(bpver)} | sensitivity {len(sens)}")
print(f"{OUT_G}: {[r['label'] for r in g]}")
