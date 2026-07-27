"""
Adapter: v6 campaign results -> the grouped shape the figure scripts expect.

The figure set was redesigned to an art-editor specification and that visual
identity must be preserved (revision protocol, non-negotiable decision 3).
The v6 campaign stores a flat `runs` list, whereas ieee_figures.py expects the
v4 grouping (`frontier`, `lambda_sweep`, `sensitivity`, ...). Rather than
rewrite the plotting code -- which would risk changing the design -- this
regroups the v6 records into the v4 shape and writes campaign_results_v6.json.
The record schema itself is unchanged between versions, so no field mapping is
needed except for the per-scenario operating metrics, which were renamed.

Only runs that exist are emitted; a figure whose series is missing will fail
loudly rather than plot a partial curve silently.

Usage: python3 figdata_v6.py [in.json] [out.json]
"""

import json
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "campaign_v5_results.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "campaign_results_v6.json"

d = json.load(open(SRC))
runs = [r for r in d["runs"] if "error" not in r and not r.get("infeasible")]
by = {r["label"]: r for r in runs}

FRONTIER = [l for l in ("eps_1.00", "eps_0.70", "eps_0.50", "eps_0.35",
                        "eps_0.20", "eps_0.10", "eps_0.00") if l in by]
LAMS = sorted((l for l in by if re.match(r"^lam_\d+$", l)),
              key=lambda l: float(l.split("_")[1]))
BPS = sorted((l for l in by if l.startswith("bp_lam_")),
             key=lambda l: float(l.split("_")[-1]))
SENS = [l for l in by if re.match(
    r"^(ffh_om_|ffh_capex_|grid_|batt_|derate_|reserve_|spare_|precond_tau_)", l)]

# the economic baseline is lambda = 0 and belongs at the head of the sweep
sweep = ([dict(by["econ_lam0"], label="lam_0")] if "econ_lam0" in by else []) \
    + [by[l] for l in LAMS]

# per-scenario operating metrics: v6 field names -> the ones the figures use
ops = {}
for w, v in (d.get("ops_metrics_policy") or {}).items():
    ops[w] = {"min_reserve_kWh_p5": v.get("p5_reserve_kWh"),
              "min_reserve_kWh_min": v.get("min_reserve_kWh"),
              "plug_hours_used": v.get("plug_hours"),
              "reassigned_blocks_vs_mildest": v.get("reassigned_vs_first")}

# v4 label spellings, which the figure scripts index by name
ALIAS = {"econ_lam0": "econ_lambda0", "policy_lam100": "policy_lambda100"}

out = {
    "runs": [dict(by[l], label=ALIAS[l])
             for l in ("econ_lam0", "policy_lam100") if l in by],
    "ops_metrics_policy": ops,
    "sensitivity": [by[l] for l in sorted(SENS)],
    "monotonicity_flags": [],
    "frontier": [by[l] for l in FRONTIER],
    "lambda_sweep": sweep,
    "breakpoint_verification": [by[l] for l in BPS],
    "n_minus_1": by.get("n_minus_1"),
    "_provenance": {"source": SRC, "n_runs": len(runs),
                    "hosts": sorted({r.get("host", "?") for r in runs})},
}
json.dump(out, open(DST, "w"), indent=1)
print(f"{DST}: frontier {len(out['frontier'])} | sweep {len(sweep)} | "
      f"breakpoints {len(BPS)} | sensitivity {len(SENS)} | "
      f"n-1 {'yes' if out['n_minus_1'] else 'no'}")
missing = [k for k in ("frontier", "lambda_sweep", "sensitivity") if not out[k]]
if missing:
    print("MISSING series:", missing)
