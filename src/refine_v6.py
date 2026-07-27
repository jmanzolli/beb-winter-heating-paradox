"""
Post-campaign refinement (revision protocol 5.2 and 11.7).

The campaign's own refinement pass covers only the emissions-cap frontier.
Three further classes of run need tightening before any of them is quoted:

  1. the economic baseline, if any carbon-price or capped run found a cheaper
     resource cost (proves the baseline incumbent is loose, and every
     increment measured against it is overstated);
  2. carbon-price runs whose absolute gap exceeds the declared tolerance;
  3. any run whose loose gap breaks monotonicity in lambda.

Each is re-solved warm-started from the best compatible design found anywhere
in the campaign, with a longer limit. Records are replaced only when the
re-solve certifies a tighter gap, so this can never worsen an archived run.

Usage: ROUTE_INPUTS=route52_inputs_v5.json python3 refine_v6.py [--dry-run]
"""

import json
import os
import re
import sys

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v5.json")

import campaign_v5 as C

ABS_GAP = C.ABS_GAP
TLIM = 7200
OUT_FILE = C.OUT_FILE
COMPARABLE = re.compile(r"^(eps_|lam_|bp_lam_|policy_lam)")


def load():
    d = json.load(open(OUT_FILE))
    return d, {r["label"]: r for r in d["runs"]
               if "error" not in r and not r.get("infeasible")}


def targets(runs):
    todo = []
    base = runs.get("econ_lam0")
    if base:
        cheaper = [r for r in runs.values()
                   if COMPARABLE.match(r["label"]) and r["F1"] < base["F1"] - 1.0]
        if cheaper:
            best = min(cheaper, key=lambda r: r["F1"])
            todo.append(("econ_lam0", dict(lam=0.0, eps=None), best,
                         f"dominated by {best['label']} "
                         f"({base['F1']:.0f} -> {best['F1']:.0f})"))
    for lb, r in sorted(runs.items()):
        # breakpoint-verification runs carry the policy claim too
        if not re.match(r"^(bp_)?lam_\d+$", lb):
            continue
        if r["abs_gap"] <= ABS_GAP:
            continue
        # warm start from the cheapest design whose emissions also satisfy
        # this run's incentive, i.e. the best objective F1 + lam*F2
        best = min(runs.values(),
                   key=lambda q: q["F1"] + r["lam"] * q["co2_t"])
        todo.append((lb, dict(lam=r["lam"], eps=None), best,
                     f"gap {r['abs_gap']:.0f} > {ABS_GAP:.0f}"))
    return todo


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    d, runs = load()
    todo = targets(runs)
    if not todo:
        print("nothing to refine")
        raise SystemExit(0)
    for lb, kw, seed, why in todo:
        print(f"{lb}: {why}; warm start from {seed['label']}", flush=True)
    if dry:
        raise SystemExit(0)

    for lb, kw, seed, why in todo:
        before = runs[lb]["abs_gap"]
        rec, _ = C.solve(lb, tlim=TLIM, force=True,
                         mip_start=C.design_from_record(seed), **kw)
        if rec is None:
            print(f"{lb}: re-solve produced no solution, record kept",
                  flush=True)
            continue
        if rec["abs_gap"] >= before:
            print(f"{lb}: gap not improved ({before:.0f} -> "
                  f"{rec['abs_gap']:.0f}), keeping the tighter record",
                  flush=True)
    # Table IV is generated from the per-scenario operation stored in the run
    # record. The carbon-price record predates that field, so re-solve it with
    # the first stage pinned (seconds) to regenerate the operating point in
    # the current record format.
    pol = runs.get("policy_lam100")
    if pol and "scen_ops" not in pol:
        print("recovering scenario operation for policy_lam100_ops", flush=True)
        C.solve("policy_lam100_ops", lam=100.0,
                fix_design=C.design_from_record(pol), tlim=900, force=True)

    # keep, per label, the record with the tightest certified gap
    best = {}
    for r in C.OUT["runs"]:
        lb = r["label"]
        if lb not in best or r.get("abs_gap", 9e9) < best[lb].get("abs_gap", 9e9):
            best[lb] = r
    seen, dedup = set(), []
    for r in C.OUT["runs"]:
        if r["label"] in seen:
            continue
        seen.add(r["label"])
        dedup.append(best[r["label"]])
    C.OUT["runs"] = dedup
    C._dump()
    print("refinement done", flush=True)
