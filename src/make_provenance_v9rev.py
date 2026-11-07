"""Extend provenance_v9.json with the review runs of 2026-11-06.

The five new Route 52 solves (ffh_capex_7500/10000/12500, eps_0.10r,
det_designday) were logged to logs_rev/ by run_review_v9.sh; this script adds
one record per run in the format of make_provenance_v5.py and writes
provenance_v9rev.json.

Usage: PROV_LOGDIR=logs_rev python3 make_provenance_v9rev.py
"""
import json
import os

BASE = os.environ.get("PROV_BASE", "provenance_v9.json")
RES = os.environ.get("PROV_RES", "campaign_v9rev_results.json")
LOGDIR = os.environ.get("PROV_LOGDIR", "logs_rev")
OUT = os.environ.get("PROV_OUT", "provenance_v9rev.json")
MIN_LINES = 20


def log_lines(name):
    p = os.path.join(LOGDIR, f"{name}.log")
    if not os.path.exists(p):
        return 0
    with open(p, errors="ignore") as f:
        return sum(1 for _ in f)


P = json.load(open(BASE))
runs = [r for r in json.load(open(RES))["runs"] if "error" not in r]
for r in runs:
    lb = r["label"]
    if lb in P["runs"]:
        continue
    n = log_lines(lb)
    ph2 = r.get("phase2")
    P["runs"][lb] = {
        "archive_level": "search_log" if n >= MIN_LINES else "record_only",
        "log_lines": n, "incumbent": r["obj"], "lower_bound": r["lb"],
        "abs_gap": r["abs_gap"], "rel_gap": r["rel_gap"],
        "runtime_s": r["time_s"], "status": r["status"],
        "phase2_log": (log_lines(lb + "_ph2") or None) if ph2 else None}
full = sum(v["archive_level"] == "search_log" for v in P["runs"].values())
P["summary"] = {"n_runs": len(P["runs"]), "with_search_log": full,
                "record_only": len(P["runs"]) - full}
P["disclosure"] = (f"Solver logs are archived for all {full} of {len(P['runs'])} runs."
                   if full == len(P["runs"]) else
                   f"Solver logs are archived for {full} of {len(P['runs'])} runs; "
                   "for the others only the structured record is archived.")
json.dump(P, open(OUT, "w"), indent=1)
print(P["summary"], P["disclosure"])
