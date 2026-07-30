"""
Build the computational-provenance record (revision protocol Section 8).

For every run in campaign_v5_results.json, classify what is archived:
  "search_log"   full Gurobi search log on disk (>20 lines)
  "record_only"  structured record only (incumbent, bound, absolute and
                 relative gap, runtime, status, cost decomposition); the
                 raw search log was lost because the first campaign pass ran
                 with OutputFlag=0, which suppresses Gurobi FILE logging as
                 well as console output. Disclosed, not reconstructed.

Writes provenance_v5.json (never written by the campaign, so it is safe to
regenerate while a campaign is running) and prints the disclosure sentence
used in the manuscript's computational-reporting section.

Usage: python3 make_provenance_v5.py
"""

import json
import os

RES = os.environ.get("PROV_RES", "campaign_v5_results.json")
LOGDIR = "logs_v5"
OUT = os.environ.get("PROV_OUT", "provenance_v5.json")
MIN_LINES = 20


def log_lines(label):
    p = os.path.join(LOGDIR, f"{label}.log")
    if not os.path.exists(p):
        return 0
    with open(p, errors="ignore") as f:
        return sum(1 for _ in f)


D = json.load(open(RES))
runs = [r for r in D["runs"] if "error" not in r]
rows, n_full, n_rec = {}, 0, 0
for r in runs:
    lb = r["label"]
    n = log_lines(lb)
    lvl = "search_log" if n >= MIN_LINES else "record_only"
    n_full += lvl == "search_log"
    n_rec += lvl == "record_only"
    rows[lb] = {
        "archive_level": lvl, "log_lines": n,
        "incumbent": r.get("obj"), "lower_bound": r.get("lb"),
        "abs_gap": r.get("abs_gap"), "rel_gap": r.get("rel_gap"),
        "runtime_s": r.get("time_s"), "status": r.get("status"),
        "phase2_log": (log_lines(lb + "_ph2") >= MIN_LINES)
        if r.get("phase2") else None,
    }

meta = D.get("meta", {})
prov = {
    "runs": rows,
    "summary": {"n_runs": len(runs), "with_search_log": n_full,
                "record_only": n_rec},
    # runs are split across two machines; every record carries its own host
    "hardware": {"machine": "Apple M1 Pro / Intel Xeon Gold 6138",
                 "cores": "8 / 80", "ram_gb": "16 / 282",
                 "os": "macOS 26.5 / Ubuntu 18.04 LTS",
                 "hosts": sorted({r.get("host", "unknown") for r in runs}),
                 "note": ("baseline, frontier and carbon-price runs on the "
                          "laptop; sensitivity, refinement and division-scale "
                          "runs on the compute server")},
    "solver": {"name": "Gurobi", "version": meta.get("gurobi"),
               "interface": "gurobipy, Python 3.9.13",
               "threads": "6 (laptop) / 16-24 (server)",
               "params_changed": {
                   "MIPGapAbs": meta.get("abs_gap"),
                   "TimeLimit": "3600 s (7200 s for hard cap and price points)",
                   "Threads": "6 / 16-24",
                   "NodefileStart": "1 GB (tree spilled to disk)",
                   "NodefileDir": "gurobi_nodefiles",
                   "SoftMemLimit": "11 GB",
                   "LogToConsole": 0},
               "seed": "default (not varied)",
               "mip_start": "recorded design used as warm start in the "
                            "frontier refinement pass"},
    "disclosure": (
        f"Solver logs are archived for all {n_full} of {len(runs)} runs."
        if n_rec == 0 else
        f"Solver logs are archived for {n_full} of {len(runs)} runs; for the "
        f"remaining {n_rec} the archived record is the structured solver "
        "output captured at termination (best incumbent, best bound, absolute "
        "and relative gap, runtime, and status), which supports every "
        "reported value, but the raw search trace is not available."),
}
json.dump(prov, open(OUT, "w"), indent=1)
print(f"{len(runs)} runs | search_log {n_full} | record_only {n_rec}")
print()
print(prov["disclosure"])
