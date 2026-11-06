"""Solve one Route 52 campaign label in its own shard (v9 acceleration).

Same solve calls and limits as campaign_v9_part.py "core", one label per
process so the frontier points, carbon prices and breakpoint prices run in
parallel. Merge the shard files with merge_campaign.py afterwards.

Usage (CAMP_OUT = this shard's file; CORE_SRC = file holding econ_lam0):
  python shard_solve_v9.py eps_0.20          # lexicographic frontier point
  python shard_solve_v9.py lam_3500          # carbon-price point
  python shard_solve_v9.py bp_lam_1032       # breakpoint price
  python shard_solve_v9.py refine:eps_0.35   # refinement re-solve (MIP start)
"""
import json
import os
import sys

import campaign_v5 as C

arg = sys.argv[1]
src = os.environ.get("CORE_SRC", "sh_core_v9.json")
recs = {r["label"]: r for r in json.load(open(src))["runs"]}

if arg.startswith("eps_"):
    frac = float(arg[4:])
    co2max = recs["econ_lam0"]["co2_t"]
    C.solve(arg, eps=co2max * frac, lam=0.0, lexicographic=True,
            tlim=C.TLIM_HARD)
elif arg.startswith("lam_"):
    lamv = int(arg[4:])
    C.solve(arg, lam=float(lamv),
            tlim=C.TLIM_HARD if lamv in (3500, 10000) else C.TLIM)
elif arg.startswith("bp_lam_"):
    C.solve(arg, lam=float(arg[7:]), tlim=C.TLIM)
elif arg.startswith("refine:"):
    lb = arg.split(":", 1)[1]
    r0 = recs[lb]
    C.solve(lb, eps=r0["eps"], lam=0.0, lexicographic=True,
            tlim=C.TLIM_HARD, force=True, mip_start=C.design_from_record(r0))
else:
    sys.exit(f"unknown label {arg}")
C._dump()
print("shard", arg, "done", flush=True)
