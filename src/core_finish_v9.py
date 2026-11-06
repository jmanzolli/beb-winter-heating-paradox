"""Finish the Route 52 core part after the sharded solves (v9 acceleration).

Mirrors the bookkeeping of campaign_v9_part.py "core" on the merged core file
(CAMP_OUT): frontier_labels, breakpoint_prices, and the baseline-monotonicity
re-solve (H2). Modes:
  python core_finish_v9.py bps      print the breakpoint prices (one per line)
  python core_finish_v9.py loose    print frontier labels with abs gap > ABS_GAP
  python core_finish_v9.py final    write the keys, run H2, dedup, dump
"""
import re
import sys

import campaign_v5 as C

mode = sys.argv[1]
recs = {r["label"]: r for r in C.OUT["runs"]}
frontier = [recs[f"eps_{f:.2f}"] for f in (1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.0)
            if f"eps_{f:.2f}" in recs]
fr = sorted(frontier, key=lambda r: -r["co2_t"])
bps = []
for a, b in zip(fr, fr[1:]):
    dc, de = b["F1"] - a["F1"], a["co2_t"] - b["co2_t"]
    if de > 1e-3 and dc > 0:
        bps.append(round(dc / de, 0))
bps = sorted(set(bps))

if mode == "bps":
    for v in bps[:3]:
        print(int(v))
elif mode == "loose":
    for r in frontier:
        if r.get("abs_gap", 0) > C.ABS_GAP:
            print(r["label"])
elif mode == "final":
    C.OUT["frontier_labels"] = [r["label"] for r in frontier]
    C.OUT["breakpoint_prices"] = bps
    C._dump()
    b0 = recs.get("econ_lam0")
    cmp_ = re.compile(r"^(eps_|lam_|bp_lam_|policy_lam)")
    cheaper = [r for r in C.OUT["runs"] if cmp_.match(r["label"])
               and r.get("F1", 9e18) < b0["F1"] - 1.0]
    if cheaper:
        best = min(cheaper, key=lambda r: r["F1"])
        print(f"baseline dominated by {best['label']}; re-solving", flush=True)
        C.solve("econ_lam0", lam=0.0, tlim=C.TLIM_HARD, force=True,
                mip_start=C.design_from_record(best))
    C.dedup_runs()
    C._dump()
    print("core finished:", len(C.OUT["runs"]), "runs; breakpoints", bps)
