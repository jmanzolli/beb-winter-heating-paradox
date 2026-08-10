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
LOGDIR = os.environ.get("PROV_LOGDIR", "logs_v5")
OUT = os.environ.get("PROV_OUT", "provenance_v5.json")
MIN_LINES = 20

# Hardware description per host, so the record states where the runs actually
# happened instead of repeating a campaign-specific split. v7 was laptop plus
# server; v8 is server only. Unknown hosts fall through to their own name.
HOSTS = {
    "manager.inescc.pt": {"machine": "Intel Xeon Gold 6138", "cores": "80",
                          "ram_gb": "282", "os": "Ubuntu 18.04 LTS"},
    None: {"machine": "Apple M1 Pro", "cores": "8", "ram_gb": "16",
           "os": "macOS 26.5"},
}


def _join(vals):
    return " / ".join(str(v) for v in vals)


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

# hardware and thread counts are read off the records, so the provenance
# describes the campaign that actually ran
# infeasible runs are recorded as stubs with no solve metadata, so they carry
# no host; they must not invent a machine that never ran anything
hosts = sorted({r["host"] for r in runs if r.get("host")})
specs = [HOSTS.get(h, {"machine": str(h), "cores": "?", "ram_gb": "?",
                       "os": "?"}) for h in hosts]
threads = sorted({r["threads"] for r in runs if r.get("threads")})
hw_note = ("all runs on a single host" if len(hosts) == 1 else
           "runs split across hosts; every record carries its own host")

prov = {
    "runs": rows,
    "summary": {"n_runs": len(runs), "with_search_log": n_full,
                "record_only": n_rec},
    "hardware": {"machine": _join(s["machine"] for s in specs),
                 "cores": _join(s["cores"] for s in specs),
                 "ram_gb": _join(s["ram_gb"] for s in specs),
                 "os": _join(s["os"] for s in specs),
                 "hosts": hosts, "note": hw_note},
    "solver": {"name": "Gurobi", "version": meta.get("gurobi"),
               "interface": "gurobipy, Python 3.9.13",
               "threads": _join(threads) if threads else "unrecorded",
               "params_changed": {
                   "MIPGapAbs": meta.get("abs_gap"),
                   "TimeLimit": "3600 s (7200 s for hard cap and price points)",
                   "Threads": _join(threads) if threads else "unrecorded",
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
